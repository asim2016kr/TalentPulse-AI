"""Apply ordered, checksum-locked SQL migrations atomically; no destructive reset."""
import argparse
import hashlib
from pathlib import Path
from .db import connect

MIGRATIONS = Path(__file__).parent / 'migrations'


def migrate(connection):
    with connection.transaction():
        connection.execute('SELECT pg_advisory_xact_lock(73912401)')
        connection.execute('CREATE SCHEMA IF NOT EXISTS talentpulse_meta')
        connection.execute('REVOKE ALL ON SCHEMA talentpulse_meta FROM PUBLIC')
        connection.execute('''CREATE TABLE IF NOT EXISTS talentpulse_meta.migrations
            (name text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())''')
        for path in sorted(MIGRATIONS.glob('*.sql')):
            body = path.read_text(encoding='utf-8')
            checksum = hashlib.sha256(body.encode()).hexdigest()
            prior = connection.execute('SELECT sha256 FROM talentpulse_meta.migrations WHERE name=%s', (path.name,)).fetchone()
            if prior:
                if prior[0] != checksum:
                    raise ValueError('An applied migration changed; create a new migration')
                continue
            connection.execute(body)
            connection.execute('INSERT INTO talentpulse_meta.migrations(name,sha256) VALUES (%s,%s)', (path.name, checksum))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print('Planned migrations: ' + ', '.join(p.name for p in sorted(MIGRATIONS.glob('*.sql'))))
        return
    try:
        with connect() as connection:
            migrate(connection)
    except Exception:
        raise SystemExit('Migration failed; transaction rolled back. Check configuration and database access locally.') from None
    print('Migrations applied successfully.')


if __name__ == '__main__':
    main()
