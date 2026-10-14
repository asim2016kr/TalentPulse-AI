# Product Phase 1 validation — 2026-09-21

Implemented in the existing repository at `C:\TalentPulse-AI`:

- PostgreSQL schema: users, companies, jobs, saved jobs, applications, click events,
  ingestion provenance; indexes, constraints, timestamp triggers, private schema and
  closed RLS defaults.
- Transactional checksum-locked migration runner with a read-only plan default.
- Development seed adapter joining the existing approved snapshot to archived source
  descriptions/application URLs, guarded by manifest/review evidence checks.
- Product architecture, REST contract, page flows, production ingestion migration
  plan and free-tier/environment setup instructions.
- Root `.env.example` updated with placeholders. Actual `.env` credentials untouched.

Verification completed:

- `python -m unittest discover -s tests`: 66 discovered, 65 passed, 1 skipped.
  The 58 existing regression tests and 7 new seed tests passed.
- Seed tests cover complete source coverage, preserved review/prediction provenance,
  changed evidence rejection, duplicate/missing IDs, unsafe redirect URLs, source
  HTML stripping and incorrect snapshot size.
- `python -m product.seed_snapshot --export product/output/development_seed.json`:
  32 jobs, 30 companies, 32 descriptions, all `unverified`/development only.
- `python -m product.migrate`: correctly lists migration without connecting.
- PostgreSQL parser (`pglast` 8.4) accepted all 30 SQL statements. This validates
  syntax only; it does not prove database execution or permissions.
- Installed psycopg/psycopg-binary 3.3.6 in the existing virtual environment.

Not yet verified / external dependency:

- No PostgreSQL/Supabase connection was present; no schema was applied to a live
  database, and no seed was inserted into one.
- `tests/test_product_database.py` was skipped intentionally. It requires
  `TALENTPULSE_TEST_DATABASE_URL` pointing to an EMPTY disposable PostgreSQL database.
  It refuses an existing app/meta schema, tests migration/seed idempotence, stable
  job IDs/bookmarks, active-fixture rejection, FK protection, stale/non-development
  overwrite rejection, and rolls back all schema/data changes.
- After configuring the test URL locally, run:
  `python -m unittest discover -s tests -p test_product_database.py`.
  Do not paste the connection string into chat or commit it.
- Auth routes, job read APIs, runtime role/RLS policies and frontend routes are
  specified, not implemented. Closed RLS has no runtime access policies yet.
- Availability of historical job listings was not rechecked. The fixture is not
  approved as live job supply; Phase 2 must validate fresh data.
- No external service was provisioned, no paid plan was selected, and no application
  was deployed. Existing UI, classification files and Snowflake data were not changed.

Next external step: create a Supabase free project and configure DATABASE_URL,
SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in the root `.env` using the guide.
Keep APP_ENV=development. The database connection enables remaining Phase 1 execution
checks before Phase 2 begins production ingestion/API work.
