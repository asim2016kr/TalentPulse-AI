import json
import unittest
from pathlib import Path
from rag.analytics_assistant import QueryPlan,answer_plan,ask,catalog


def fixture():
    return dict(total_jobs=2,unique_companies=1,generated_at='2026-09-01T00:00:00Z',input_sha256='abc',source='fixture',
        distributions={'roles':[dict(value='Data Engineer',jobs=2,share_of_jobs_pct=100)],
                       'posting_dates':[dict(value='2026-08-01',jobs=2,share_of_jobs_pct=100)]},
        source_tags=[dict(value='SQL',jobs=2,share_of_jobs_pct=100)],
        role_source_tags=[dict(role='Data Engineer',source_tag='SQL',jobs=2,share_within_role_pct=100)],
        salary={'market_salary_statistics':None},coverage={},review_coverage=dict(source_rows=3,loaded_rows=2,approved_nontech_rows=1,quarantined_rows=0),
        limitations=['Snapshot only','No longitudinal history'])


class AssistantTests(unittest.TestCase):
    def plan(self,topic,entity=None):return QueryPlan(topic=topic,entity=entity,limit=5)

    def test_answer_uses_changed_report_not_hardcoded_counts(self):
        r=fixture();r['total_jobs']=123
        a=answer_plan(self.plan('overview'),r)
        self.assertIn('123 jobs',a['answer']);self.assertEqual(a['evidence'][0]['value'],123)
        self.assertEqual(a['basis']['input_sha256'],'abc')

    def test_unknown_entity_rejected(self):
        with self.assertRaises(ValueError):answer_plan(self.plan('roles','Invented'),fixture())
        with self.assertRaises(ValueError):answer_plan(self.plan('role_source_tags'),fixture())

    def test_every_citation_resolves_to_report_value(self):
        r=fixture()
        for topic in ['overview','roles','source_tags','coverage','salary','trends','role_source_tags']:
            a=answer_plan(self.plan(topic,'Data Engineer' if topic=='role_source_tags' else None),r)
            for e in a['evidence']:
                value=r
                for key in e['path'].split('.'):value=value[int(key)] if isinstance(value,list) else value[key]
                self.assertEqual(value,e['value']);self.assertIn('['+e['id']+']',a['answer'])

    def test_unavailable_topics_do_not_invent_estimates(self):
        for topic in ['salary','trends']:
            a=answer_plan(self.plan(topic),fixture());self.assertEqual(a['status'],'insufficient_data')
        self.assertEqual(answer_plan(self.plan('unsupported'),fixture())['evidence'],[])

    def test_model_cannot_supply_arbitrary_prose_or_sql(self):
        with self.assertRaises(ValueError):QueryPlan(topic='roles',entity=None,limit=5,answer='Invented claim')
        with self.assertRaises(ValueError):QueryPlan(topic='SELECT * FROM FACT_JOBS',entity=None,limit=5)
        with self.assertRaises(ValueError):QueryPlan(topic='roles',entity=None,limit=100)

    def test_input_limits_before_provider(self):
        for q in ['', ' '*10, 'x'*1001, None]:
            with self.assertRaises(ValueError):ask(q,fixture(),None)

    def test_role_tag_denominator_and_snapshot_scope(self):
        a=answer_plan(self.plan('role_source_tags','Data Engineer'),fixture())
        self.assertIn('100% within this role',a['answer'])
        self.assertIn('not verified',a['answer'])
        self.assertNotIn('input_sha256',catalog(fixture()))
