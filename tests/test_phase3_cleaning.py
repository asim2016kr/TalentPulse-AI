import tempfile
import unittest
from pathlib import Path
from ingestion.remotejobs.processing.classification_contract import write_csv
from ingestion.remotejobs.processing.clean_jobs import DataCleaner


class CleaningTests(unittest.TestCase):
    def clean(self, location, title='Software Engineer', company='Hôtel São'):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'raw.csv'
            row = dict(job_id='0001', job_title=title, company=company, location=location, tags='Python')
            write_csv(path, [row], list(row))
            cleaner = DataCleaner(path)
            cleaner.remove_missing_values()
            cleaner.preserve_missing_locations()
            cleaner.clean_text()
            cleaner.remove_empty_strings()
            return cleaner.df

    def test_blank_location_retained_and_flagged(self):
        for location in ['', '   ']:
            row = self.clean(location).iloc[0]
            self.assertEqual(row['location'], 'Unknown')
            self.assertTrue(row['location_missing'])
            self.assertEqual(row['job_id'], '0001')

    def test_real_unicode_and_location_preserved(self):
        row = self.clean('España').iloc[0]
        self.assertEqual(row['company'], 'Hôtel São')
        self.assertEqual(row['location'], 'España')
        self.assertFalse(row['location_missing'])

    def test_recoverable_mojibake_repaired(self):
        self.assertEqual(self.clean('EspaÃ±a').iloc[0]['location'], 'España')

    def test_missing_title_or_company_still_rejected(self):
        self.assertTrue(self.clean('', title='').empty)
        self.assertTrue(self.clean('', company=' ').empty)
