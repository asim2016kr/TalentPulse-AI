import unittest
from collections import Counter
from analytics.warehouse_analytics import distributions, summarize, salary_status, ranked, fact_row


class AnalyticsTests(unittest.TestCase):
    def test_connector_zero_is_preserved_for_reconciliation(self):
        row=fact_row(['id','company','place','role','category','Other','title','Unknown','Unknown',0,None,'url','2026-09-01'])
        self.assertEqual(row['salary_min'],'0')
        self.assertIsNone(row['salary_max'])

    def test_missing_partial_invalid_and_positive_salaries(self):
        cases=[('', '', 'missing_or_zero'),(0,0,'missing_or_zero'),(None,100,'partial'),
               (0,100,'partial'),(200,100,'invalid'),('NaN',100,'invalid'),(-1,5,'invalid'),
               ('bad',5,'invalid'),(100,200,'positive_range_currency_period_unverified')]
        for lo,hi,want in cases:
            with self.subTest(lo=lo,hi=hi):
                self.assertEqual(salary_status(dict(salary_min=lo,salary_max=hi)),want)

    def test_unknown_coverage_and_salary_suppression(self):
        rows=[dict(role='Data Engineer',company='A',salary_min=100,salary_max=200,
                   location='Unknown',experience_level='Other'),
              dict(role='Data Engineer',company='A',salary_min=0,salary_max=0,
                   location='London',experience_level='Senior')]
        report=summarize(rows,distributions(rows),Counter({'SQL':2,'Python':1}),Counter({('Data Engineer','SQL'):2}))
        self.assertEqual(report['total_jobs'],2)
        self.assertEqual(report['coverage']['locations']['known_pct'],50)
        self.assertEqual(report['coverage']['seniority']['unknown_jobs'],1)
        self.assertEqual(report['coverage']['work_modes']['unknown_jobs'],2)
        self.assertIsNone(report['salary']['market_salary_statistics'])
        self.assertEqual(report['source_tags'][0]['share_of_jobs_pct'],100)
        self.assertEqual(report['role_source_tags'][0]['share_within_role_pct'],100)

    def test_tag_fanout_does_not_change_job_denominator(self):
        tags=ranked({'Python':2,'SQL':2,'AWS':1},2)
        self.assertEqual(sum(r['jobs'] for r in tags),5)
        self.assertEqual(sum(r['share_of_jobs_pct'] for r in tags),250)
        self.assertEqual(tags[0]['jobs'],2)

    def test_empty_snapshot_not_published(self):
        with self.assertRaises(ValueError):summarize([],{},Counter(),Counter())

    def test_posting_dates_do_not_invent_missing_days(self):
        groups=distributions([{'date_posted':'2026-09-01'},{'date_posted':'2026-09-03'},{}])
        self.assertEqual(groups['posting_dates'],{'2026-09-01':1,'2026-09-03':1,'Unknown':1})


if __name__=='__main__':unittest.main()
