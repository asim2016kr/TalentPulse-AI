"""Opt-in integration test on an EMPTY disposable PostgreSQL database.

Set TALENTPULSE_TEST_DATABASE_URL explicitly. Never uses DATABASE_URL implicitly.
All schema/data changes roll back, including successful test writes.
"""
import os
import unittest
from uuid import uuid4


@unittest.skipUnless(os.getenv('TALENTPULSE_TEST_DATABASE_URL'), 'Disposable PostgreSQL not configured')
class ProductDatabaseTests(unittest.TestCase):
    def test_migration_seed_idempotence_constraints_and_rollback(self):
        import psycopg
        from product.migrate import migrate
        from product.seed_snapshot import build_seed, import_seed
        with psycopg.connect(os.environ['TALENTPULSE_TEST_DATABASE_URL'], prepare_threshold=None) as conn:
            exists = conn.execute("SELECT count(*) FROM pg_namespace WHERE nspname IN ('app','talentpulse_meta')").fetchone()[0]
            if exists:
                self.fail('Use an empty disposable database; refusing to test an existing schema')
            try:
                migrate(conn)
                migrate(conn)
                seed = build_seed()
                self.assertEqual(32, import_seed(conn, seed))
                ids = conn.execute('SELECT id FROM app.jobs ORDER BY id').fetchall()
                user = uuid4()
                conn.execute('INSERT INTO app.users(id,email) VALUES (%s,%s)', (user, 'test@example.com'))
                conn.execute('INSERT INTO app.saved_jobs(user_id,job_id) VALUES (%s,%s)', (user, ids[0][0]))
                self.assertEqual(32, import_seed(conn, seed))
                self.assertEqual(ids, conn.execute('SELECT id FROM app.jobs ORDER BY id').fetchall())
                self.assertEqual(1, conn.execute('SELECT count(*) FROM app.saved_jobs').fetchone()[0])
                self.assertEqual(30, conn.execute('SELECT count(*) FROM app.companies').fetchone()[0])
                with self.assertRaises(psycopg.errors.CheckViolation):
                    with conn.transaction():
                        conn.execute("UPDATE app.jobs SET status='active',freshness_checked_at=now(),fresh_until=now()+interval '7 days'")
                with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    with conn.transaction():
                        conn.execute('DELETE FROM app.jobs WHERE id=%s', (ids[0][0],))
                conn.execute('UPDATE app.jobs SET is_development=false WHERE id=%s', (ids[0][0],))
                with self.assertRaisesRegex(ValueError, 'Refusing'):
                    import_seed(conn, seed)
                self.assertEqual(1, conn.execute('SELECT count(*) FROM app.jobs WHERE NOT is_development').fetchone()[0])
            finally:
                conn.rollback()
            self.assertEqual(0, conn.execute("SELECT count(*) FROM pg_namespace WHERE nspname IN ('app','talentpulse_meta')").fetchone()[0])
