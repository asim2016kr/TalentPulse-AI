"""Stage immutable source snapshots and import explicitly reviewed, fresh listings.

Capture/review staging never alters the historical classification/warehouse files.
No missing-feed deletion, automatic review approval, or Snowflake dual write.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import requests
from psycopg import sql
from psycopg.types.json import Jsonb

from ingestion.remotejobs.fetch_jobs import RemoteJobsIngestion
from ingestion.remotejobs.processing.clean_jobs import DataCleaner
from ingestion.remotejobs.processing.classification_contract import (Classification, VERSION, prepare_source,
    read_csv, source_hash, write_csv)
from ingestion.remotejobs.processing.transform_jobs import transform
from .db import ROOT
from .seed_snapshot import description_text, source_url

BASELINE_RAW = ROOT / 'data/snapshots/20260915T062929Z/source_jobs.json'
BASELINE_REVIEW = ROOT / 'ingestion/output/reviewed_jobs.csv'
CHECK_WINDOW = timedelta(days=7)


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone required')
    return parsed.astimezone(timezone.utc)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def semantic_content(row):
    """Exact substantive evidence, excluding two provider-generated tracking tokens.

    Remote OK changes its source tracking token per API caller. Normalize ONLY the
    two token positions in its recognized application appendix, preserving all job
    text and the requested application word. Any other change requires re-review.
    """
    result={k:row.get(k) for k in ['id','position','company','location','tags','description','url','apply_url','date','salary_min','salary_max']}
    result['id']=str(row.get('id',''))
    text=result['description'] or ''
    prefix,separator,footer=text.rpartition('Please mention the word')
    if separator and 'when applying to show you read the job post completely' in footer and 'Companies can search these words' in footer:
        footer=re.sub(r'\btag [A-Za-z0-9+/=]+(?=\s)','tag [SOURCE_TRACKING_TOKEN]',footer)
        footer=re.sub(r'\(#[A-Za-z0-9+/=]+\)', '(#[SOURCE_TRACKING_TOKEN])',footer)
        result['description']=prefix+separator+footer
    return result


def source_index(raw):
    if not isinstance(raw, list) or not raw:
        raise ValueError('Empty/malformed source feed')
    result = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError('Malformed source record')
        if 'id' not in item:
            continue
        key = str(item['id'])
        if not key or key in result:
            raise ValueError('Missing/duplicate source ID')
        result[key] = item
    if not result:
        raise ValueError('Source feed contains no jobs')
    return result


def capture(directory=None,previous_run=None):
    """One bounded request to the existing fixed provider API; retain its terms header."""
    now = datetime.now(timezone.utc)
    directory = Path(directory or ROOT / 'product/output/runs' / (now.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]))
    directory.mkdir(parents=True, exist_ok=False)
    with requests.get('https://remoteok.com/api', timeout=(10,30),stream=True,
                      headers={'User-Agent':'TalentPulse/0.1','Accept':'application/json'}) as response:
        response.raise_for_status()
        chunks=[]; size=0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 20_000_000:
                raise ValueError('Source payload exceeds limit')
            chunks.append(chunk)
    body=b''.join(chunks)
    raw=json.loads(body); source_index(raw)
    path=directory/'source_jobs.json'; path.write_bytes(body)
    metadata={'source':'remoteok','source_url':'https://remoteok.com/api','observed_at':now.isoformat(),
              'snapshot_sha256':sha(path),'source_rows':len(source_index(raw)),
              'source_terms':raw[0].get('legal','') if 'id' not in raw[0] else '',
              'feed_is_complete':False}
    (directory/'snapshot.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    stage(directory,previous_run)
    return directory


def stage(directory,previous_run=None):
    directory=Path(directory)
    raw=json.loads((directory/'source_jobs.json').read_bytes())
    by_id=source_index(raw)
    metadata=json.loads((directory/'snapshot.json').read_text(encoding='utf-8'))
    if metadata['snapshot_sha256'] != sha(directory/'source_jobs.json'):
        raise ValueError('Archived snapshot changed')
    # Reuse existing ingestion/cleaning behavior, with isolated output paths.
    frame=RemoteJobsIngestion().transform_jobs(list(by_id.values()))
    frame.to_csv(directory/'raw_jobs.csv',index=False,encoding='utf-8-sig')
    cleaner=DataCleaner(directory/'raw_jobs.csv')
    for method in ['remove_duplicates','remove_missing_values','preserve_missing_locations','clean_text',
                   'clean_skills','clean_urls','standardize_dates','remove_empty_strings']:
        getattr(cleaner,method)()
    cleaner.df.to_csv(directory/'clean_jobs.csv',index=False,encoding='utf-8-sig')
    clean,_=read_csv(directory/'clean_jobs.csv'); clean=prepare_source(clean)
    if previous_run:
        previous_run=Path(previous_run)
        prior_raw=previous_run/'source_jobs.json'
        prior_review=previous_run/'reviewed_jobs.csv'
        prior_metadata=json.loads((previous_run/'snapshot.json').read_text(encoding='utf-8'))
        if prior_metadata['snapshot_sha256']!=sha(prior_raw):
            raise ValueError('Previous source archive changed')
    else:
        prior_raw,prior_review=BASELINE_RAW,BASELINE_REVIEW
    baseline=json.loads(prior_raw.read_bytes()); old=source_index(baseline)
    previous,fields=read_csv(prior_review); reviews={r['job_id']:r for r in previous}
    old_sha=sha(prior_raw)
    output=[]
    for row in clean:
        identifier=row['job_id']; prior=reviews.get(identifier)
        unchanged=(identifier in old and semantic_content(old[identifier])==semantic_content(by_id[identifier]))
        if (prior and unchanged and prior.get('review_source_sha256')==old_sha
                and prior.get('input_hash')==source_hash(prior)==source_hash(row)
                and prior.get('classifier_version')==VERSION and prior.get('classification_status')=='ok'
                and prior.get('reviewer','').strip() and prior.get('review_status') in {'approved','quarantined'}):
            result=dict(prior); result.update(row)
            result.update(input_hash=source_hash(row),review_source_sha256=metadata['snapshot_sha256'],
                          review_evidence=str(directory/'source_jobs.json')+'#job_id='+identifier,
                          review_note=prior['review_note']+' | Prior review carried forward: unchanged substantive source evidence; provider tracking tokens normalized.')
        else:
            result=dict.fromkeys(fields,''); result.update(row)
            result.update(input_hash=source_hash(row),review_status='pending',classification_status='pending',
                          classifier_version=VERSION,needs_review='True',
                          review_source_sha256=metadata['snapshot_sha256'],
                          review_note='New or changed source evidence; classification/review required.')
        output.append(result)
    fields=list(dict.fromkeys(fields+list(clean[0]) if clean else fields))
    write_csv(directory/'reviewed_jobs.csv',output,fields)
    report={'source_rows':len(by_id),'clean_rows':len(clean),
            'carried_reviews':sum(r['review_status'] in {'approved','quarantined'} for r in output),
            'pending_reviews':sum(r['review_status']=='pending' for r in output)}
    (directory/'stage_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def check_listing(url, title):
    """Validate fixed-provider source-page accessibility, not employer vacancy truth."""
    url=source_url(url)
    checked=datetime.now(timezone.utc)
    current=url; outcome='unverified'
    try:
        for _ in range(4):
            with requests.get(current,timeout=(10,20),allow_redirects=False,stream=True,
                              headers={'User-Agent':'TalentPulse/0.1'}) as response:
                if response.status_code in {301,302,303,307,308}:
                    from urllib.parse import urljoin
                    current=source_url(urljoin(current,response.headers.get('Location','')))
                    continue
                if response.status_code in {404,410}:
                    outcome='expired'; break
                if response.status_code!=200:
                    break
                chunks=[]; size=0
                for part in response.iter_content(65536):
                    size+=len(part)
                    if size>3_000_000:
                        raise ValueError('Page limit exceeded')
                    chunks.append(part)
                text=description_text(b''.join(chunks).decode('utf-8',errors='replace'))
                if re.search(r'\b(this job (?:is|has been) (?:closed|expired)|position has been filled)\b',text,re.I):
                    outcome='expired'
                elif ' '.join(title.split()).casefold() in ' '.join(text.split()).casefold():
                    outcome='source_accessible'
                break
    except (requests.RequestException,ValueError):
        pass  # Evidence remains unverified; transport failure never confirms expiry.
    return {'url':url,'checked_at':checked.isoformat(),'outcome':outcome}


def checks(directory):
    directory=Path(directory)
    rows,_=read_csv(directory/'reviewed_jobs.csv')
    clean,_=read_csv(directory/'clean_jobs.csv')
    chosen=[r for r in rows if r.get('review_status')=='approved' and r.get('classification_status')=='ok']
    chosen_ids={r['job_id'] for r in chosen}
    eligible=transform(chosen,[r for r in clean if r['job_id'] in chosen_ids])
    result={}
    for row in eligible:
        result[row['job_id']]=check_listing(row['url'],row['job_title'])
    evidence={'snapshot_sha256':sha(directory/'source_jobs.json'),'checks':result}
    (directory/'link_checks.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    return {'checked':len(result),'outcomes':{o:sum(r['outcome']==o for r in result.values())
             for o in ['source_accessible','expired','unverified']}}


def classify_pending(directory):
    from .db import ROOT
    from dotenv import load_dotenv
    from ingestion.remotejobs.processing.ai_classifier import classify
    from ingestion.remotejobs.processing.model_provider import configured_predictor
    load_dotenv(ROOT/'.env')
    directory=Path(directory)
    reviews,fields=read_csv(directory/'reviewed_jobs.csv')
    clean,_=read_csv(directory/'clean_jobs.csv')
    pending={r['job_id'] for r in reviews if r['review_status']=='pending'}
    rows=[r for r in clean if r['job_id'] in pending]
    if not rows:
        return {'classified':0,'errors':0}
    with configured_predictor() as (provider,model,predict):
        output=classify(rows,model,predict,directory/'.classification_cache',provider=provider)
    classified={r['job_id']:r for r in output}
    raw_sha=sha(directory/'source_jobs.json')
    final=[]
    for original in reviews:
        row=dict(original)
        if row['job_id'] in classified:
            row.update(classified[row['job_id']])
            row.update(review_source_sha256=raw_sha,review_evidence=str(directory/'source_jobs.json')+'#job_id='+row['job_id'])
        final.append(row)
    fields=list(dict.fromkeys(fields+[k for row in final for k in row]))
    write_csv(directory/'reviewed_jobs.csv',final,fields)
    return {'classified':len(output),'errors':sum(r['classification_status']=='error' for r in output)}


def prepare_batch(directory, now=None):
    directory=Path(directory); now=now or datetime.now(timezone.utc)
    metadata=json.loads((directory/'snapshot.json').read_text(encoding='utf-8'))
    raw_sha=sha(directory/'source_jobs.json')
    if metadata['source']!='remoteok' or metadata['snapshot_sha256']!=raw_sha:
        raise ValueError('Source identity/hash mismatch')
    observed=utc(metadata['observed_at'])
    if observed>now+timedelta(minutes=5) or now-observed>timedelta(days=1):
        raise ValueError('Fresh source snapshot required')
    raw=source_index(json.loads((directory/'source_jobs.json').read_bytes()))
    clean,_=read_csv(directory/'clean_jobs.csv'); clean=prepare_source(clean)
    reviewed,_=read_csv(directory/'reviewed_jobs.csv')
    source={r['job_id']:r for r in clean}
    ids=[r.get('job_id') for r in reviewed]
    if len(set(ids))!=len(ids) or set(ids)!=set(source) or not set(source)<=set(raw):
        raise ValueError('Review/clean/source identity coverage mismatch')
    if any(r['input_hash']!=source_hash(source[r['job_id']]) or source_hash(r)!=r['input_hash'] for r in reviewed):
        raise ValueError('Reviewed source changed')
    selected=[r for r in reviewed if r.get('review_status')=='approved']
    if any(r.get('review_source_sha256')!=raw_sha for r in selected):
        raise ValueError('Description evidence differs from approved review')
    chosen_ids={r['job_id'] for r in selected}
    rows=transform(selected,[r for r in clean if r['job_id'] in chosen_ids])
    evidence=json.loads((directory/'link_checks.json').read_text(encoding='utf-8')) if (directory/'link_checks.json').exists() else {'checks':{}}
    if evidence.get('snapshot_sha256',raw_sha)!=raw_sha:
        raise ValueError('Link evidence belongs to a different snapshot')
    jobs=[]
    for row in rows:
        item=raw[row['job_id']]; url=source_url(item['url'])
        # Restrict all destinations to attributed source pages for this provider.
        check=evidence['checks'].get(row['job_id'])
        status='unverified'; checked=None; fresh_until=None
        if check:
            checked=utc(check['checked_at'])
            if check['url']!=url or checked<observed-timedelta(minutes=5) or checked>now+timedelta(minutes=5) or now-checked>timedelta(days=1):
                raise ValueError('Invalid/stale link evidence')
            if check['outcome']=='source_accessible':
                status='active'; fresh_until=(min(checked,observed)+CHECK_WINDOW).isoformat()
            elif check['outcome']=='expired':
                status='expired'
            elif check['outcome']!='unverified':
                raise ValueError('Unknown link-check outcome')
        jobs.append({'source':'remoteok','source_job_id':row['job_id'],
            'company_key':'remoteok:name:'+row['company'].strip().casefold(),'company_name':row['company'],
            'title':row['job_title'],'description_text':description_text(item['description']),
            'source_url':url,'application_url':url,'application_url_kind':'source_listing',
            'location_text':None if row['location']=='Unknown' else row['location'],
            'work_mode':row['work_mode'],'job_type':row['job_type'],'role':row['role'],
            'category':row['category'],'experience_level':row['experience_level'],
            'source_tags':row['tags'].split(', ') if row['tags'] else [],
            'classification':{**{k:row[k] for k in Classification.model_fields},
                'original_prediction':json.loads(row['original_prediction']),'provider':row['ai_provider'],
                'model':row['ai_model'],'version':row['classifier_version'],'reviewer':row['reviewer'],
                'reviewed_at':row['reviewed_at'],'review_note':row['review_note'],'evidence_sha256':raw_sha},
            'review_status':'approved','source_content_sha256':hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'published_at':utc(item['date']).isoformat(),'first_seen_at':observed.isoformat(),
            'last_seen_at':observed.isoformat(),'freshness_checked_at':checked.isoformat() if checked else None,
            'fresh_until':fresh_until,'status':status,'is_development':False,
            'status_reason':{'active':'Present in current source feed; source page accessible. Employer availability unconfirmed.',
                'expired':'Source page reports closure or is missing.','unverified':'Source link/availability checks pending or inconclusive.'}[status]})
    return {'source':'remoteok','snapshot_sha256':raw_sha,'reviewed_sha256':sha(directory/'reviewed_jobs.csv'),
            'observed_at':observed.isoformat(),'is_development':False,'jobs':jobs,
            'pending_reviews':sum(r['review_status']=='pending' for r in reviewed),
            'suspend_ids':sorted(set(ids)-{j['source_job_id'] for j in jobs})}


def import_batch(connection,batch):
    if not batch['jobs'] and not batch.get('suspend_ids'):
        raise ValueError('Nothing eligible to import; complete review first')
    with connection.transaction():
        connection.execute('SELECT pg_advisory_xact_lock(73912402)')
        for job in batch['jobs']:
            prior=connection.execute('SELECT last_seen_at FROM app.jobs WHERE source=%s AND source_job_id=%s',
                                     (job['source'],job['source_job_id'])).fetchone()
            if prior and prior[0]>utc(batch['observed_at']):
                raise ValueError('Refusing an older source snapshot')
        if batch.get('suspend_ids'):
            # New adverse/uncertain evidence disables older published entries.
            # Feed omissions are excluded from this list and never mass-expire jobs.
            connection.execute("""UPDATE app.jobs SET status='unverified',fresh_until=NULL,
                status_reason='Current source evidence requires review or no longer qualifies.'
                WHERE source=%s AND source_job_id=ANY(%s) AND last_seen_at<=%s AND NOT is_development""",
                (batch['source'],batch['suspend_ids'],batch['observed_at']))
        run=connection.execute('''INSERT INTO app.ingestion_runs
            (source,snapshot_sha256,reviewed_sha256,observed_at,is_development,imported_count)
            VALUES(%s,%s,%s,%s,false,%s) ON CONFLICT(source,snapshot_sha256,reviewed_sha256)
            DO UPDATE SET imported_count=EXCLUDED.imported_count RETURNING id''',
            (batch['source'],batch['snapshot_sha256'],batch['reviewed_sha256'],batch['observed_at'],len(batch['jobs']))).fetchone()[0]
        for job in batch['jobs']:
            company=connection.execute('''INSERT INTO app.companies(identity_key,name) VALUES(%s,%s)
                ON CONFLICT(identity_key) DO UPDATE SET name=EXCLUDED.name RETURNING id''',
                (job['company_key'],job['company_name'])).fetchone()[0]
            data={k:v for k,v in job.items() if k not in {'company_key','company_name'}}
            data.update(company_id=company,ingestion_run_id=run); data['classification']=Jsonb(data['classification'])
            columns=list(data); updates=[k for k in columns if k not in {'source','source_job_id','first_seen_at'}]
            query=sql.SQL('INSERT INTO app.jobs({}) VALUES({}) ON CONFLICT(source,source_job_id) DO UPDATE SET {}').format(
                sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(sql.Placeholder() for _ in columns),
                sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(k),sql.Identifier(k)) for k in updates))
            connection.execute(query,list(data.values()))
        count=connection.execute('SELECT count(*) FROM app.jobs WHERE ingestion_run_id=%s',(run,)).fetchone()[0]
        if count!=len(batch['jobs']):
            raise ValueError('Post-import reconciliation failed')
        connection.execute('INSERT INTO app.analytics_exports(ingestion_run_id) VALUES(%s) ON CONFLICT DO NOTHING',(run,))
    return count


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['capture','classify-pending','check-links','plan','apply'])
    parser.add_argument('--run',type=Path)
    parser.add_argument('--previous-run',type=Path,help='Prior reviewed run; otherwise use the original development review')
    args=parser.parse_args()
    try:
        if args.action=='capture':
            print('Staged source run:',capture(args.run,args.previous_run)); return
        if not args.run:
            parser.error('--run is required')
        if args.action=='classify-pending':
            print(json.dumps(classify_pending(args.run),indent=2)); return
        if args.action=='check-links':
            print(json.dumps(checks(args.run),indent=2)); return
        batch=prepare_batch(args.run)
        if args.action=='apply':
            from .db import connect_ingestion
            with connect_ingestion() as connection:
                import_batch(connection,batch)
        print(json.dumps({'mode':args.action,'jobs':len(batch['jobs']),
            'active':sum(j['status']=='active' for j in batch['jobs']),'pending_reviews':batch['pending_reviews']},indent=2))
    except Exception as error:
        # Never serialize connection/provider exception bodies.
        raise SystemExit('Ingestion failed ('+type(error).__name__+'); no partial database import committed.') from None


if __name__=='__main__':
    main()
