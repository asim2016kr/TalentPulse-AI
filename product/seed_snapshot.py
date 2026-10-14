"""Import the reviewed 32-job development fixture, never publish it as live jobs.

Default: validate and print a plan without connecting. --export writes a UI fixture.
--apply requires APP_ENV=development and the initial migration already applied.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from ftfy import fix_encoding
from ingestion.remotejobs.processing.transform_jobs import skills
from warehouse.reload_validation import preflight
from .db import ROOT, connect

SNAPSHOT = ROOT / 'data/snapshots/20260915T062929Z/source_jobs.json'
TRANSFORMED = ROOT / 'ingestion/output/transformed_jobs.csv'
OBSERVED_AT = '2026-09-15T06:29:29+00:00'


def source_url(value):
    """This seed only trusts Remote OK source links; no arbitrary redirect target."""
    parts = urlsplit(value)
    if (parts.scheme != 'https' or parts.hostname not in {'remoteok.com', 'www.remoteok.com'}
            or parts.username or parts.password or parts.port not in {None, 443}
            or not parts.path.startswith('/remote-jobs/')
            or any(c.isspace() or ord(c) < 32 for c in value) or '\\' in value):
        raise ValueError('Invalid Remote OK source/application URL')
    return value


def description_text(value):
    soup = BeautifulSoup(fix_encoding(value), 'html.parser')
    for tag in soup(['script', 'style', 'iframe', 'object', 'noscript']):
        tag.decompose()
    text = '\n'.join(line.strip() for line in soup.get_text('\n').splitlines() if line.strip())
    if not text:
        raise ValueError('A full source description is required')
    return text


def prepare(rows, manifest, raw, raw_sha256):
    by_id = {}
    for item in raw:
        if 'id' not in item:  # provider metadata header, if present
            continue
        identifier = str(item['id'])
        if identifier in by_id:
            raise ValueError('Duplicate archived source ID')
        by_id[identifier] = item
    if len(rows) != 32:
        raise ValueError('This development seed requires exactly the reviewed 32 jobs')
    jobs = []
    for row in rows:
        if row['review_source_sha256'] != raw_sha256:
            raise ValueError('Archived descriptions differ from the reviewed evidence')
        source = by_id.get(row['job_id'])
        if source is None:
            raise ValueError('Reviewed job missing from archived source')
        link = source_url(source['url'])
        application = source_url(source.get('apply_url') or link)
        posted = datetime.fromisoformat(source['date'].replace('Z', '+00:00'))
        if posted.tzinfo is None:
            raise ValueError('Source posting timestamp needs a timezone')
        jobs.append({
            'source': 'remoteok', 'source_job_id': row['job_id'],
            'company_key': 'remoteok:name:' + row['company'].strip().casefold(),
            'company_name': row['company'], 'title': row['job_title'],
            'description_text': description_text(source['description']),
            'source_url': link, 'application_url': application,
            'application_url_kind': 'source_listing',
            'location_text': None if row['location'] == 'Unknown' else row['location'],
            'work_mode': row['work_mode'], 'job_type': row['job_type'],
            'role': row['role'], 'category': row['category'], 'experience_level': row['experience_level'],
            'source_tags': skills(row['tags']),
            'classification': {
                'is_tech_job': True, 'role': row['role'], 'category': row['category'],
                'experience_level': row['experience_level'],
                'original_prediction': json.loads(row['original_prediction']),
                'model': row['ai_model'], 'provider': row['ai_provider'],
                'version': row['classifier_version'], 'classified_at': row['classified_at'],
                'reviewer': row['reviewer'], 'reviewed_at': row['reviewed_at'],
                'review_note': row['review_note'],
                'review_evidence_sha256': raw_sha256,
            },
            'review_status': 'approved',
            'source_content_sha256': hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            'published_at': posted.astimezone(timezone.utc).isoformat(),
            'first_seen_at': OBSERVED_AT, 'last_seen_at': OBSERVED_AT,
            'status': 'unverified', 'status_reason': 'Historical development snapshot; availability not checked',
            'is_development': True,
        })
    return {'source': 'remoteok', 'snapshot_sha256': raw_sha256,
            'reviewed_sha256': manifest['reviewed_sha256'], 'observed_at': OBSERVED_AT,
            'is_development': True, 'jobs': jobs}


def build_seed():
    rows, manifest = preflight(TRANSFORMED)
    raw_bytes = SNAPSHOT.read_bytes()
    return prepare(rows, manifest, json.loads(raw_bytes), hashlib.sha256(raw_bytes).hexdigest())


def import_seed(connection, seed):
    from psycopg.types.json import Jsonb
    if seed.get('is_development') is not True or any(
            j.get('status') != 'unverified' or j.get('is_development') is not True for j in seed['jobs']):
        raise ValueError('Seed importer cannot publish active listings')
    with connection.transaction():
        connection.execute('SELECT pg_advisory_xact_lock(73912402)')
        # Never overwrite a listing that was subsequently refreshed/promoted.
        for job in seed['jobs']:
            prior = connection.execute('''SELECT is_development,last_seen_at FROM app.jobs
                WHERE source=%s AND source_job_id=%s''', (job['source'], job['source_job_id'])).fetchone()
            if prior and (not prior[0] or prior[1] > datetime.fromisoformat(seed['observed_at'])):
                raise ValueError('Refusing to overwrite a newer or non-development listing')
        run = connection.execute('''INSERT INTO app.ingestion_runs
            (source,snapshot_sha256,reviewed_sha256,observed_at,is_development,imported_count)
            VALUES (%s,%s,%s,%s,true,%s)
            ON CONFLICT(source,snapshot_sha256,reviewed_sha256) DO UPDATE SET imported_count=EXCLUDED.imported_count
            RETURNING id''', (seed['source'], seed['snapshot_sha256'], seed['reviewed_sha256'],
                              seed['observed_at'], len(seed['jobs']))).fetchone()[0]
        for job in seed['jobs']:
            company = connection.execute('''INSERT INTO app.companies(identity_key,name)
                VALUES (%s,%s) ON CONFLICT(identity_key) DO UPDATE SET name=EXCLUDED.name RETURNING id''',
                (job['company_key'], job['company_name'])).fetchone()[0]
            data = {k: v for k, v in job.items() if k not in {'company_key', 'company_name'}}
            data.update(company_id=company, ingestion_run_id=run)
            data['classification'] = Jsonb(data['classification'])
            # Column names are internal constants from prepare(), never user input.
            from psycopg import sql
            columns = list(data)
            updates = [k for k in columns if k not in {'source','source_job_id','first_seen_at'}]
            statement = sql.SQL('''INSERT INTO app.jobs ({}) VALUES ({})
                ON CONFLICT(source,source_job_id) DO UPDATE SET {}''').format(
                sql.SQL(',').join(map(sql.Identifier, columns)),
                sql.SQL(',').join(sql.Placeholder() for _ in columns),
                sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(k), sql.Identifier(k)) for k in updates))
            connection.execute(statement, list(data.values()))
        actual = connection.execute('SELECT count(*) FROM app.jobs WHERE ingestion_run_id=%s', (run,)).fetchone()[0]
        if actual != len(seed['jobs']):
            raise ValueError('Seed reconciliation failed; rolling back')
    return actual


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--export', type=Path)
    args = parser.parse_args()
    try:
        seed = build_seed()
        if args.export:
            args.export.parent.mkdir(parents=True, exist_ok=True)
            args.export.write_text(json.dumps(seed, indent=2, ensure_ascii=False), encoding='utf-8')
        if args.apply:
            if os.getenv('APP_ENV') != 'development':
                raise ValueError('APP_ENV must be development')
            with connect() as connection:
                import_seed(connection, seed)
    except Exception:
        raise SystemExit('Seed failed; no database transaction committed. Check APP_ENV, snapshot validation and database configuration locally.') from None
    print(json.dumps({'mode': 'applied' if args.apply else 'offline_plan',
                      'jobs': len(seed['jobs']), 'companies': len({j['company_key'] for j in seed['jobs']}),
                      'descriptions': sum(bool(j['description_text']) for j in seed['jobs']),
                      'status': 'unverified', 'is_development': True,
                      'snapshot_sha256': seed['snapshot_sha256']}, indent=2))


if __name__ == '__main__':
    main()
