import hashlib
import json
import unittest
from product.seed_snapshot import (SNAPSHOT, TRANSFORMED, build_seed, description_text,
                                   prepare, source_url)
from warehouse.reload_validation import preflight


class ProductSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SNAPSHOT.exists() or not TRANSFORMED.exists():
            raise unittest.SkipTest('Private archived snapshot required; not distributed in Git')
        cls.rows, cls.manifest = preflight(TRANSFORMED)
        cls.raw = json.loads(SNAPSHOT.read_bytes())
        cls.raw_hash = hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()

    def test_real_seed_complete_and_not_published(self):
        seed = build_seed()
        self.assertEqual(32, len(seed['jobs']))
        self.assertEqual(30, len({j['company_key'] for j in seed['jobs']}))
        self.assertEqual(32, len({j['source_job_id'] for j in seed['jobs']}))
        for job in seed['jobs']:
            self.assertTrue(job['description_text'].strip())
            self.assertTrue(job['is_development'])
            self.assertEqual('unverified', job['status'])
            self.assertEqual('source_listing', job['application_url_kind'])
            self.assertEqual(seed['observed_at'], job['last_seen_at'])
            self.assertIn('original_prediction', job['classification'])

    def test_changed_description_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'differ'):
            prepare(self.rows, self.manifest, self.raw, '0' * 64)

    def test_missing_and_duplicate_source_ids_fail_closed(self):
        selected = self.rows[0]['job_id']
        missing = [r for r in self.raw if str(r.get('id')) != selected]
        with self.assertRaisesRegex(ValueError, 'missing'):
            prepare(self.rows, self.manifest, missing, self.raw_hash)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            prepare(self.rows, self.manifest, self.raw + [self.raw[0]], self.raw_hash)

    def test_wrong_snapshot_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '32'):
            prepare(self.rows[:-1], self.manifest, self.raw, self.raw_hash)

    def test_unsafe_external_redirects_are_rejected(self):
        for value in ['javascript:alert(1)', 'http://remoteok.com/remote-jobs/a',
                      'https://remoteok.com.evil.test/remote-jobs/a',
                      'https://user@remoteok.com/remote-jobs/a',
                      'https://127.0.0.1/remote-jobs/a',
                      'https://remoteok.com:444/remote-jobs/a',
                      'https://remoteok.com/remote-jobs/a\r\nX: header',
                      'https://remoteok.com\\@evil.test/remote-jobs/a']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                source_url(value)
        self.assertEqual('https://remoteOK.com/remote-jobs/a', source_url('https://remoteOK.com/remote-jobs/a'))

    def test_source_html_is_plain_text_not_executable_markup(self):
        value = description_text('<h2>Engineer</h2><script>alert(1)</script><p>Build pipelines.</p>')
        self.assertEqual('Engineer\nBuild pipelines.', value)
        with self.assertRaises(ValueError):
            description_text('<script>only script</script>')

    def test_original_prediction_and_corrected_role_are_both_preserved(self):
        seed = build_seed()
        original_by_id = {r['job_id']: r for r in self.rows}
        for job in seed['jobs']:
            row = original_by_id[job['source_job_id']]
            self.assertEqual(row['role'], job['role'])
            self.assertEqual(json.loads(row['original_prediction']), job['classification']['original_prediction'])


if __name__ == '__main__':
    unittest.main()
