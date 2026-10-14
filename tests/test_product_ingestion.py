import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from product.ingestion import BASELINE_RAW,BASELINE_REVIEW,semantic_content,source_index,prepare_batch
from ingestion.remotejobs.processing.classification_contract import read_csv,write_csv


class ProductIngestionTests(unittest.TestCase):
    def fixture(self,path):
        if not BASELINE_RAW.exists() or not BASELINE_REVIEW.exists():
            self.skipTest('Private archived snapshot required; not distributed in Git')
        path=Path(path); now=datetime.now(timezone.utc)
        raw=BASELINE_RAW.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
        (path/'source_jobs.json').write_bytes(raw)
        (path/'snapshot.json').write_text(json.dumps({'source':'remoteok','snapshot_sha256':digest,
            'observed_at':now.isoformat()}),encoding='utf-8')
        from product.db import ROOT
        (path/'clean_jobs.csv').write_bytes((ROOT/'ingestion/output/clean_jobs.csv').read_bytes())
        (path/'reviewed_jobs.csv').write_bytes(BASELINE_REVIEW.read_bytes())
        return now

    def test_only_known_provider_tracking_tokens_can_change_without_review(self):
        old={'id':'1','description':'Build data pipelines. Please mention the word **TEST** and tag RAABBCC123456 when applying to show you read the job post completely (#RAABBCC123456). Companies can search these words to find applicants.'}
        new=copy.deepcopy(old); new['id']=1; new['description']=new['description'].replace('RAABBCC123456','RXXYYZZ987654')
        self.assertEqual(semantic_content(old),semantic_content(new))
        padded=copy.deepcopy(old)
        padded['description']=padded['description'].replace('RAABBCC123456','RXXYYZZ987654==')
        self.assertEqual(semantic_content(old),semantic_content(padded))
        new['description']=new['description'].replace('Build data pipelines.','Manage payroll.')
        self.assertNotEqual(semantic_content(old),semantic_content(new))
        new=copy.deepcopy(old);new['description']=new['description'].replace('**TEST**','**CHANGED**')
        self.assertNotEqual(semantic_content(old),semantic_content(new))

    def test_duplicate_feed_ids_and_empty_feed_rejected(self):
        for raw in [[],[{'id':1},{'id':'1'}],[None]]:
            with self.assertRaises(ValueError):source_index(raw)

    def test_without_link_evidence_reviewed_jobs_are_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            now=self.fixture(tmp); batch=prepare_batch(tmp,now)
            self.assertEqual(32,len(batch['jobs']))
            self.assertTrue(all(j['status']=='unverified' for j in batch['jobs']))
            self.assertTrue(all(j['fresh_until'] is None for j in batch['jobs']))

    def test_link_evidence_controls_active_expired_and_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            now=self.fixture(tmp);batch=prepare_batch(tmp,now)
            outcomes=['source_accessible','expired','unverified']
            links={j['source_job_id']:{'url':j['source_url'],'checked_at':now.isoformat(),
                    'outcome':outcomes[n%3]} for n,j in enumerate(batch['jobs'])}
            (Path(tmp)/'link_checks.json').write_text(json.dumps({'snapshot_sha256':batch['snapshot_sha256'],'checks':links}),encoding='utf-8')
            checked=prepare_batch(tmp,now)
            self.assertEqual(['active','expired','unverified'],[j['status'] for j in checked['jobs'][:3]])
            self.assertEqual((now+timedelta(days=7)).isoformat(),checked['jobs'][0]['fresh_until'])

    def test_tampered_evidence_and_stale_snapshot_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            now=self.fixture(tmp)
            with self.assertRaisesRegex(ValueError,'Fresh'):
                prepare_batch(tmp,now+timedelta(days=2))
            rows,fields=read_csv(Path(tmp)/'reviewed_jobs.csv');rows[0]['job_title']='Changed after review'
            write_csv(Path(tmp)/'reviewed_jobs.csv',rows,fields)
            with self.assertRaisesRegex(ValueError,'changed'):
                prepare_batch(tmp,now)

    def test_pending_and_nontech_do_not_publish_and_source_omissions_do_not_expire(self):
        with tempfile.TemporaryDirectory() as tmp:
            now=self.fixture(tmp);before=prepare_batch(tmp,now)
            rows,fields=read_csv(Path(tmp)/'reviewed_jobs.csv')
            candidate=before['jobs'][0]['source_job_id']
            for row in rows:
                if row['job_id']==candidate: row['review_status']='pending'
            write_csv(Path(tmp)/'reviewed_jobs.csv',rows,fields)
            after=prepare_batch(tmp,now)
            self.assertEqual(31,len(after['jobs']))
            self.assertIn(candidate,after['suspend_ids'])
            self.assertNotIn('not-present-in-source-feed',after['suspend_ids'])
