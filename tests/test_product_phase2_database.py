"""Transactional tests against configured, migrated PostgreSQL; no test writes persist."""
import os
import unittest
from datetime import datetime,timedelta,timezone
from uuid import uuid4


@unittest.skipUnless(os.getenv('TALENTPULSE_PHASE2_TEST_DATABASE_URL'),'Phase 2 PostgreSQL test URL not configured')
class ProductPhase2DatabaseTests(unittest.TestCase):
    def test_runtime_roles_restrict_private_data_and_ingestion_is_atomic(self):
        import psycopg
        from product.seed_snapshot import build_seed
        from product.ingestion import import_batch
        with psycopg.connect(os.environ['TALENTPULSE_PHASE2_TEST_DATABASE_URL'],prepare_threshold=None) as conn:
            baseline=conn.execute('SELECT count(*) FROM app.jobs').fetchone()[0]
            try:
                seed=build_seed();jobs=seed['jobs'][:2]
                now=datetime.now(timezone.utc)
                for j in jobs:
                    j.update(source_job_id='integration-'+uuid4().hex,is_development=False,status='active',
                        first_seen_at=now.isoformat(),last_seen_at=now.isoformat(),freshness_checked_at=now.isoformat(),
                        fresh_until=(now+timedelta(days=7)).isoformat())
                batch={**seed,'snapshot_sha256':uuid4().hex*2,'reviewed_sha256':uuid4().hex*2,
                    'observed_at':now.isoformat(),'is_development':False,'jobs':jobs,'suspend_ids':[]}
                self.assertEqual(2,import_batch(conn,batch))
                first=conn.execute('SELECT id FROM app.jobs WHERE source_job_id=%s',(jobs[0]['source_job_id'],)).fetchone()[0]
                self.assertEqual(2,import_batch(conn,batch))
                self.assertEqual(first,conn.execute('SELECT id FROM app.jobs WHERE source_job_id=%s',(jobs[0]['source_job_id'],)).fetchone()[0])
                with conn.transaction():
                    conn.execute('SET LOCAL ROLE talentpulse_read')
                    self.assertEqual(0,conn.execute('SELECT count(*) FROM app.jobs WHERE is_development').fetchone()[0])
                    self.assertEqual(1,conn.execute('SELECT count(*) FROM app.jobs WHERE id=%s',(first,)).fetchone()[0])
                conn.execute('RESET ROLE')
                for query in ['SELECT * FROM app.users','SELECT classification FROM app.jobs',"UPDATE app.jobs SET title='changed'"]:
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        with conn.transaction():
                            conn.execute('SET LOCAL ROLE talentpulse_read');conn.execute(query)
                invalid={**batch,'snapshot_sha256':uuid4().hex*2,'jobs':[dict(j) for j in jobs]}
                invalid['jobs'][1]['application_url']='javascript:alert(1)'
                invalid['jobs'][0]['title']='Should roll back'
                with self.assertRaises(psycopg.errors.CheckViolation):
                    import_batch(conn,invalid)
                self.assertNotEqual('Should roll back',conn.execute('SELECT title FROM app.jobs WHERE id=%s',(first,)).fetchone()[0])
                older={**batch,'observed_at':(now-timedelta(days=1)).isoformat()}
                with self.assertRaisesRegex(ValueError,'older'):import_batch(conn,older)
                suspend={**batch,'snapshot_sha256':uuid4().hex*2,'jobs':[],'suspend_ids':[jobs[0]['source_job_id']]}
                self.assertEqual(0,import_batch(conn,suspend))
                self.assertEqual('unverified',conn.execute('SELECT status FROM app.jobs WHERE id=%s',(first,)).fetchone()[0])
            finally:
                conn.rollback()
            self.assertEqual(baseline,conn.execute('SELECT count(*) FROM app.jobs').fetchone()[0])
