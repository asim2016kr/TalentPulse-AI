"""Provision restricted server logins and save generated URLs locally, without printing secrets."""
import argparse
import os
import secrets
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from dotenv import load_dotenv, set_key
from psycopg import sql
from .db import ROOT, connect


def provision(connection, preview=False):
    """Only new, dedicated logins. Refuse credential rotation on an existing login."""
    load_dotenv(ROOT / '.env')
    if preview and os.getenv('APP_ENV') != 'development':
        raise ValueError('Preview access requires APP_ENV=development')
    parts = urlsplit(os.environ['DATABASE_URL'])
    user = unquote(parts.username or '')
    # Supabase pooler users are postgres.<project>; direct users are postgres.
    suffix = '.' + user.split('.', 1)[1] if '.' in user else ''
    names = [('talentpulse_api', 'APP_DATABASE_URL', ['talentpulse_read']),
             ('talentpulse_worker', 'INGEST_DATABASE_URL', ['talentpulse_ingest']),
             ('talentpulse_accounts', 'MEMBER_DATABASE_URL', ['talentpulse_member'])]
    if preview:
        names[0][2].append('talentpulse_preview')
    urls = {}
    with connection.transaction():
        connection.execute('SELECT pg_advisory_xact_lock(73912403)')
        for login, variable, memberships in names:
            existing = connection.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (login,)).fetchone()
            if existing:
                # Verify existing locally configured credentials separately; never reset silently.
                if not os.getenv(variable):
                    raise ValueError('Existing login has no matching local configuration; recover credentials locally')
                continue
            password = secrets.token_urlsafe(36)
            connection.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(
                sql.Identifier(login), sql.Literal(password)))
            for membership in memberships:
                connection.execute(sql.SQL('GRANT {} TO {}').format(sql.Identifier(membership), sql.Identifier(login)))
            host = parts.hostname
            if ':' in host:
                host = '[' + host + ']'
            netloc = quote(login + suffix, safe='') + ':' + quote(password, safe='') + '@' + host
            if parts.port:
                netloc += ':' + str(parts.port)
            urls[variable] = urlunsplit((parts.scheme, netloc, parts.path, parts.query, ''))
    # DB and filesystem cannot share one transaction. On write failure, new role
    # passwords must be recovered/rotated locally; they are never printed to logs.
    for variable, value in urls.items():
        set_key(ROOT / '.env', variable, value)
    return list(urls)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--development-preview', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print('Plan: provision restricted talentpulse_api and talentpulse_worker logins.')
        return
    try:
        with connect() as connection:
            provision(connection, args.development_preview)
    except Exception:
        raise SystemExit('Access setup failed. No credentials printed; inspect role/configuration state locally before retrying.') from None
    print('Restricted server database access configured locally.')


if __name__ == '__main__':
    main()
