"""Server-side connections. Never echo a connection string or driver exception."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def tls_options():
    ca = os.getenv('DATABASE_CA_CERT','').strip()
    return {'sslmode':'verify-full','sslrootcert':str(ROOT/ca)} if ca else {}


def connect():
    import psycopg
    load_dotenv(ROOT / '.env')
    url = os.environ.get('DATABASE_URL', '').strip()
    if not url or 'YOUR_' in url:
        raise ValueError('Configure DATABASE_URL in the root .env first')
    return psycopg.connect(url, connect_timeout=15, prepare_threshold=None, **tls_options())


def connect_ingestion():
    import psycopg
    load_dotenv(ROOT / '.env')
    url = os.getenv('INGEST_DATABASE_URL', '').strip()
    if not url or 'YOUR_' in url:
        raise ValueError('Configure restricted INGEST_DATABASE_URL first')
    connection = psycopg.connect(url, connect_timeout=15, prepare_threshold=None, **tls_options())
    try:
        safe = connection.execute("""SELECT NOT rolsuper AND NOT rolbypassrls AND
            pg_has_role(current_user,'talentpulse_ingest','MEMBER')
            FROM pg_roles WHERE rolname=current_user""").fetchone()[0]
        if not safe:
            raise ValueError('Unsafe ingestion role')
        connection.commit()
        return connection
    except Exception:
        connection.close()
        raise
