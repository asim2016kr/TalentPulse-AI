"""Read-only, reconciled analytics for the current approved warehouse snapshot."""
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ingestion.remotejobs.processing.transform_jobs import skills
from warehouse.reload_validation import preflight, verify_snapshot

BASE = '''FROM FACT_JOBS f
JOIN DIM_COMPANY c ON c.COMPANY_ID=f.COMPANY_ID
JOIN DIM_LOCATION l ON l.LOCATION_ID=f.LOCATION_ID
JOIN DIM_ROLE r ON r.ROLE_ID=f.ROLE_ID'''
GROUPS = {
    'roles': ('r.ROLE_NAME', 'role'), 'categories': ('r.CATEGORY', 'category'),
    'seniority': ('r.EXPERIENCE_LEVEL', 'experience_level'),
    'companies': ('c.COMPANY_NAME', 'company'), 'locations': ('l.LOCATION_NAME', 'location'),
    'work_modes': ('f.WORK_MODE', 'work_mode'), 'job_types': ('f.JOB_TYPE', 'job_type'),
    'posting_dates': ('TO_CHAR(f.POSTED_DATE, \'YYYY-MM-DD\')', 'date_posted'),
}
FACT_FIELDS = ['job_id','company','location','role','category','experience_level','job_title',
               'job_type','work_mode','salary_min','salary_max','url','date_posted']
FACT_SQL = '''SELECT f.SOURCE_JOB_ID,c.COMPANY_NAME,l.LOCATION_NAME,r.ROLE_NAME,r.CATEGORY,
r.EXPERIENCE_LEVEL,f.JOB_TITLE,f.JOB_TYPE,f.WORK_MODE,f.SALARY_MIN,f.SALARY_MAX,f.JOB_URL,
TO_CHAR(f.POSTED_DATE, 'YYYY-MM-DD') ''' + BASE
TAG_SQL = '''SELECT s.SKILL_NAME, COUNT(DISTINCT f.SOURCE_JOB_ID)
FROM FACT_JOB_SKILLS b JOIN FACT_JOBS f ON f.JOB_ID=b.JOB_ID
JOIN DIM_SKILL s ON s.SKILL_ID=b.SKILL_ID GROUP BY s.SKILL_NAME'''
ROLE_TAG_SQL = '''SELECT r.ROLE_NAME,s.SKILL_NAME,COUNT(DISTINCT f.SOURCE_JOB_ID)
FROM FACT_JOB_SKILLS b JOIN FACT_JOBS f ON f.JOB_ID=b.JOB_ID
JOIN DIM_ROLE r ON r.ROLE_ID=f.ROLE_ID
JOIN DIM_SKILL s ON s.SKILL_ID=b.SKILL_ID GROUP BY r.ROLE_NAME,s.SKILL_NAME'''


def label(value):
    return str(value).strip() if value is not None and str(value).strip() else 'Unknown'


def salary_status(row):
    values = [row.get(k) for k in ['salary_min','salary_max']]
    parsed=[]
    for v in values:
        if v is None or str(v).strip()=='': parsed.append(None); continue
        try: n=Decimal(str(v))
        except InvalidOperation: return 'invalid'
        if not n.is_finite() or n<0: return 'invalid'
        parsed.append(n)
    low,high=parsed
    if all(v is None or v==0 for v in parsed): return 'missing_or_zero'
    if any(v is None or v==0 for v in parsed): return 'partial'
    if low>high: return 'invalid'
    return 'positive_range_currency_period_unverified'


def fact_row(values):
    row=dict(zip(FACT_FIELDS,values))
    # Match the existing CSV reconciliation contract: numeric zero must remain '0', not a falsy missing value.
    for field in ['salary_min','salary_max']:
        if row[field] is not None: row[field]=str(row[field])
    return row


def distributions(rows):
    return {name:Counter(label(r.get(field)) for r in rows) for name,(_,field) in GROUPS.items()}


def ranked(counts, denominator):
    return [dict(value=k,jobs=v,share_of_jobs_pct=round(100*v/denominator,2) if denominator else 0)
            for k,v in sorted(counts.items(),key=lambda p:(-p[1],p[0]))]


def summarize(rows, groups, tags, role_tags):
    total=len(rows)
    if not total: raise ValueError('Cannot publish analytics for an empty snapshot')
    salaries=Counter(salary_status(r) for r in rows)
    coverage={}
    for name in ['locations','work_modes','job_types','seniority']:
        unknown=groups[name].get('Unknown',0)+(groups[name].get('Other',0) if name=='seniority' else 0)
        coverage[name]=dict(known_jobs=total-unknown,unknown_jobs=unknown,known_pct=round(100*(total-unknown)/total,2))
    role_totals=groups['roles']
    return dict(total_jobs=total,unique_companies=len(groups['companies']),coverage=coverage,
        salary=dict(status_counts=dict(salaries),market_salary_statistics=None,
                    suppression_reason='Currency and pay period are absent from the warehouse; positive ranges are not comparable salary estimates.'),
        distributions={k:ranked(v,total) for k,v in groups.items()},
        source_tags=ranked(tags,total),
        role_source_tags=[dict(role=role,source_tag=tag,jobs=n,share_within_role_pct=round(100*n/role_totals[role],2))
                          for (role,tag),n in sorted(role_tags.items(),key=lambda p:(p[0][0],-p[1],p[0][1]))],
        limitations=[
            'Current approved RemoteOK snapshot only; no claim of complete or representative market coverage.',
            'Posting dates describe records present in this snapshot, not longitudinal hiring growth; missing days are not zero demand.',
            'Source tags are unverified labels, not certified skills. Tag shares overlap and do not sum to 100%.',
            'Location strings are unparsed source labels, not standardized countries or cities.',
            'Unknown work modes and job types remain unknown; source website does not imply remote work.',
            'Classification was reviewed by the assistant, not independently human-annotated ground truth.',
        ])


def collect(connection, input_path):
    expected,manifest=preflight(input_path)
    query_ids=[]
    with connection.cursor() as cur:
        def query(sql):
            cur.execute(sql);query_ids.append(cur.sfqid);return cur.fetchall()
        if tuple(query('SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()')[0])!=('TALENTPULSE','JOB_ANALYTICS'):
            raise ValueError('Unexpected warehouse target')
        counts=verify_snapshot(cur,expected)
        rows=[fact_row(r) for r in query(FACT_SQL)]
        # Guard against a concurrent reload after the initial reconciliation.
        from warehouse.reload_validation import expected_facts
        if expected_facts(rows)!=expected_facts(expected):
            raise ValueError('Warehouse changed during analytics extraction')
        groups={}
        for name,(expr,_) in GROUPS.items():
            result=query(f"SELECT COALESCE(NULLIF(TRIM({expr}), ''), 'Unknown'), COUNT(*) {BASE} GROUP BY 1")
            groups[name]=dict(result)
        tags=dict(query(TAG_SQL))
        role_tags={(role,tag):n for role,tag,n in query(ROLE_TAG_SQL)}
        expected_tags=Counter(s for r in expected for s in skills(r['tags']))
        expected_role_tags=Counter((r['role'],s) for r in expected for s in skills(r['tags']))
        if groups!=distributions(expected) or tags!=expected_tags or role_tags!=expected_role_tags:
            raise ValueError('SQL aggregates differ from the approved snapshot; report not published')
    report=summarize(rows,groups,tags,role_tags)
    report.update(generated_at=datetime.now(timezone.utc).isoformat(),
        source='Snowflake TALENTPULSE.JOB_ANALYTICS',input_sha256=manifest['output_sha256'],
        validation=dict(exact_snapshot_reconciliation=True,sql_aggregate_reconciliation=True,
                        table_counts=counts,query_ids=query_ids),
        review_coverage=dict(source_rows=manifest['source_rows'],loaded_rows=len(rows),
                            approved_nontech_rows=manifest['approved_nontech_rows'],quarantined_rows=manifest['quarantined_rows']))
    return report


def markdown(report):
    lines=['# TalentPulse AI — warehouse analytics','',f"Generated: {report['generated_at']}",'',
        f"**{report['total_jobs']} approved jobs across {report['unique_companies']} companies.**",
        'Results describe the current snapshot; they are not market-wide demand estimates.','',
        '## Data coverage','','| Attribute | Known jobs | Unknown jobs | Known coverage |',
        '|---|---:|---:|---:|']
    for k,v in report['coverage'].items():
        lines.append(f"| {k.replace('_',' ')} | {v['known_jobs']} | {v['unknown_jobs']} | {v['known_pct']}% |")
    lines+=['','Salary statistics are withheld because currency and pay period are unavailable. Zero values are treated as missing for coverage.',
            '',f"Salary quality: `{json.dumps(report['salary']['status_counts'],sort_keys=True)}`."]
    for name in ['roles','categories','seniority','companies','locations','work_modes','job_types','posting_dates']:
        values=report['distributions'][name]
        if name=='posting_dates': values=sorted(values,key=lambda r:r['value'])
        lines+=['',f"## {name.replace('_',' ').title()}",'','| Source label | Jobs | Share of all jobs |','|---|---:|---:|']
        for r in values:
            value=r['value'].replace('|','\\|').replace('\n',' ')
            lines.append(f"| {value} | {r['jobs']} | {r['share_of_jobs_pct']}% |")
    lines+=['','## Top source tags','','These are unverified source tags. Each job is counted once per exact tag; shares overlap.','',
            '| Tag | Jobs | Share of all jobs |','|---|---:|---:|']
    for r in report['source_tags'][:20]:
        lines.append(f"| {r['value'].replace('|',' / ')} | {r['jobs']} | {r['share_of_jobs_pct']}% |")
    lines+=['','## Limits','']+['- '+s for s in report['limitations']]
    lines+=['','## Validation','', 'Exact warehouse facts, dimension references and tag links matched the reviewed input. All SQL aggregates matched independent local calculations.',
        '',f"Input SHA-256: `{report['input_sha256']}`.",'',
        'The JSON report includes all tags, role/tag combinations, review coverage, table counts and query IDs.']
    return '\n'.join(lines)+'\n'


def save(report, directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    for name,content in [('warehouse_analytics.json',json.dumps(report,indent=2,ensure_ascii=False)),
                         ('warehouse_analytics.md',markdown(report))]:
        path=directory/name;temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(content,encoding='utf-8');temp.replace(path)
