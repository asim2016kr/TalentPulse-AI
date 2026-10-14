# TalentPulse product Phase 2 — database, listings and read API

Completed core backend work on 2026-10-04 in the existing `C:\TalentPulse-AI`
repository. Phase 3 is the job-search website; this phase delivers its data/API.

## Result

- Supabase PostgreSQL **17.11** connection verified. Fixed literal connection-string
  template delimiters locally; no credentials printed or copied to deliverables.
- Both migrations applied: application schema and restricted access roles/outbox.
- Historical seed imported: **32 jobs / 30 companies**, all with descriptions.
- Fresh Remote OK snapshot captured October 4, 2026, at **08:00:47 UTC**
  (13:30:47 Asia/Kolkata): 99 source jobs retained in an isolated run directory.
- 73 previous reviews carried forward for unchanged substantive evidence. The only
  description differences were Remote OK's changing request tracking tokens. The
  adapter normalizes only the two token positions in the recognized source appendix;
  changes to the actual job description, application word, tags, location, dates,
  salary values or identity require re-review.
- Of those carried reviews, **24 are approved technology jobs**, 44 approved
  nontechnology jobs and 5 quarantined. All 24 technology source pages were accessible
  and contained the expected title; no closure signal was detected.
- All **26 new postings classified successfully with configured Gemini**, no provider
  errors. Predictions: 16 technology / 10 nontechnology. All remain pending explicit
  review and are withheld from the application database/public API.
- Fresh approved listings upserted with the worker role: **24 active, non-development
  jobs**. Stable job UUIDs preserved. The 8 historical jobs absent from the feed remain
  unverified development records, not declared expired.
- Current PostgreSQL totals: 32 jobs, 30 companies, 0 missing descriptions, one
  pending analytics export checkpoint. No user records/bookmarks were created by the
  persistent import; integration-test records were rolled back.

The current supply is a small, single-source MVP dataset. Presence in the current
feed plus an accessible source page confirms a source listing, not an employer's
promise that the vacancy remains open. Detail responses explain that applicants
must confirm availability on Remote OK. No independent human classification audit
was performed; inherited reviews are attributed to the earlier Codex source review.

## Running API

Next.js 16.3.8 / React 19.3.0 / pg 8.23.1, with a committed npm lockfile.
No job-board pages exist yet. The old analytics prototype remains separate.

```powershell
Set-Location C:\TalentPulse-AI\web
npm ci
npm run build
npm run start
```

The local server binds `127.0.0.1:3000`. It is running at handoff time; restart it
with the commands above if the task/session or machine is restarted. API examples:

```text
GET http://127.0.0.1:3000/api/v1/health
GET http://127.0.0.1:3000/api/v1/jobs?page_size=20&page=1
GET http://127.0.0.1:3000/api/v1/jobs?role=Software%20Engineer
GET http://127.0.0.1:3000/api/v1/jobs?q=python&sort=relevance
GET http://127.0.0.1:3000/api/v1/jobs/filters
GET http://127.0.0.1:3000/api/v1/jobs/<uuid>
```

Success/list/error structures follow `docs/PRODUCT_PHASE1.md`. List supports keyword,
company, location, role, category, seniority, work mode, job type and exact source-tag
filters, bounded pagination, newest or relevance ordering. Parameters are validated
and bound, never interpolated as SQL data. All filters combine with AND. Search
uses PostgreSQL full-text title/description matching plus an escaped company-name
match. Location is literal source text; Unknown is not inferred to mean remote.
Count and result queries share a repeatable-read transaction and identical predicates.

List/filter visibility: approved active non-development records with fresh_until
in the future and no elapsed explicit expiry. Detail may expose formerly published
stale/expired records with Apply disabled. Unverified/development IDs return 404
under normal runtime settings. Public fields omit review internals, source IDs,
credentials and raw HTML. Job descriptions are plain text. Source tags remain
unverified source metadata, not a list of verified required skills.

All routes are uncached JSON, have nosniff headers and safe errors. API handlers
never call Gemini or Snowflake. Secrets and source ingestion stay on the backend.
`can_apply` is data eligibility for Phase 4; no Apply click/mutation route is implemented
yet. User/auth/save/tracker handlers are planned for Phase 5. `/` returns Next.js's
default not-found page until the Phase 3 website is implemented.

## Access and TLS

Applied `002_ingestion_and_read_roles.sql` creates three NOLOGIN membership roles:

| Role | Access |
|---|---|
| `talentpulse_read` | SELECT public job/company columns. RLS excludes development and unverified jobs. No user-table access, no classification internals, no writes. |
| `talentpulse_preview` | Explicit development-only job/company reads. Never used by the normal production runtime. |
| `talentpulse_ingest` | Upsert companies/jobs/runs and insert analytics export checkpoints; no private user/action access. |

Server-only credentials generated for `talentpulse_api` and `talentpulse_worker` and
saved to the local root `.env` as APP_DATABASE_URL and INGEST_DATABASE_URL. The API
uses only APP_DATABASE_URL, checks role flags and rejects privileged/ingestion
connections, opens read-only transactions and SET LOCAL ROLE talentpulse_read.
No owner credential fallback. Supabase's public Data API receives no app-schema grants.
User data remains closed until Phase 5 provisions authenticated-user policies.

Both Python and Node verify the Supabase CA and hostname. Public certificate is at
`product/certs/prod-ca-2021.crt`, downloaded over HTTPS from
`https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt`.
DATABASE_CA_CERT points to that file. Certificate verification was exercised live;
rejectUnauthorized is true. No global TLS bypass was introduced. Deployment must
include this public CA file or provide an equivalent trusted certificate configuration.

Actual credentials are in `.env` only, ignored by Git. They are not in outputs or the
frontend bundle. Root .env.example documents required variables. The local launcher
loads the root .env server-side; a deployed Next.js service needs explicitly configured
environment variables. No deployment/account-plan change was performed.

## Ingestion workflow

Implemented `product/ingestion.py` keeps raw, cleaned, reviewed and checked files per
run. It reuses existing Python cleaning/classification functions; historical pipeline
files remain unchanged. Capture has a bounded provider request/payload. Description
HTML is converted to plain text with executable elements removed.

```powershell
Set-Location C:\TalentPulse-AI
# New snapshot. On subsequent runs, choose your previous reviewed run explicitly.
.\venv\Scripts\python.exe -m product.ingestion capture --previous-run product\output\runs\20261004T080047Z-175fbf98
# Use the newly printed run directory for the following commands:
.\venv\Scripts\python.exe -m product.ingestion classify-pending --run <new-run-directory>
```

Classification does not approve a job. Review the archived source description and
model output; correct labels using the existing classification contract, set
review_status=approved (or quarantined with an evidence note), reviewer, reviewed_at
and review_note in reviewed_jobs.csv. Keep original_prediction intact, source fields
unchanged and review_source_sha256 equal to the archived source hash. Record clear
review evidence. Pending/failed/quarantined/nontech records never publish.

```powershell
.\venv\Scripts\python.exe -m product.ingestion check-links --run <new-run-directory>
.\venv\Scripts\python.exe -m product.ingestion plan --run <new-run-directory>
.\venv\Scripts\python.exe -m product.ingestion apply --run <new-run-directory>
```

Plan is offline/read-only. Apply uses the restricted worker and a single transaction.
It validates identity coverage, reviewed source hashes, classifier version, review
status and raw-description evidence. Fresh source snapshots/link evidence must be
under 24 hours old; future timestamps beyond a five-minute skew are rejected. Source
pages use fixed approved Remote OK hosts and bounded redirects/responses/timeouts.
Destination URLs currently always point to Remote OK source pages; employer-host
redirect discovery is deferred. Provider throttling/HTTP errors stay unverified.

Imported accessible listings receive a seven-day recheck deadline measured from
observation/check time. Requests immediately hide stale rows even if the next batch
is late. Import rejects older observations and reconciles imported job counts before
commit. It preserves UUIDs, first_seen_at, company metadata, user saves and trackers.
New uncertain/adverse evidence for a previously active ID suspends its visibility.
Feed omissions never cause deletion or mass expiry. Explicit 404/410/closed-source
evidence for checked eligible IDs records expired status. No source-wide cleanup
or destructive table reload is used.

The initial seed importer remains a development-only bootstrap. After jobs have
been refreshed, it intentionally refuses to overwrite newer/non-development rows.
Use the production adapter for subsequent imports; do not rerun the old seed as a
refresh command. Migration runner is repeatable/checksum-locked and append-only.

Every production ingestion commit inserts an idempotent analytics-export checkpoint
in the same transaction. Snowflake remains downstream. **The export consumer and
scheduled ingestion are not implemented in this phase**; the checkpoint is pending.
Historical Snowflake/dashboard analytics still represent the earlier 32-job snapshot.
Do not treat those analytics as the current job-board inventory. Export processing
and scheduling must be completed before claiming automatic pipeline operation.

## Validation

Passed:

- PostgreSQL Phase 1 integration test on the initially empty Supabase app schema:
  migrations/repeat seed, stable IDs/bookmark preservation, FK/check enforcement,
  stale/non-development overwrite protection and rollback. 1 test, passed.
- PostgreSQL Phase 2 transactional integration test: production upsert idempotence,
  stable IDs, read-role visibility, private-field/user/write denial, atomic rollback
  on invalid records, older-snapshot rejection and suspension. 1 test, passed;
  temporary data fully rolled back.
- Full Python suite: 73 discovered, 71 passed, 2 opt-in database tests skipped in the
  ordinary run. Those same two database tests were executed separately and passed.
- 6 new ingestion tests cover source tracking normalization, duplicate IDs, pending
  review exclusion, link evidence states, changed evidence and stale-snapshot rejection.
- 5 TypeScript tests: query bounds, SQL parameter safety/literal search wildcards,
  preview denial in production, exact filters and credential-safe errors.
- TypeScript/Next.js production build passed. npm installation reported no known
  dependency vulnerabilities at installation time; this is not a full security audit.
- 29 actual HTTP checks: readiness; database/HTTP count reconciliation; all observed
  role filters; filter choices; pagination ordering/no duplicates; job descriptions;
  company and relevance queries; query-like injection input; excluded development ID;
  missing/malformed IDs; invalid bounds, sort and filters. All passed against Supabase.
- Fresh-source link checks: 24 checked, 24 source_accessible, 0 expired, 0 inconclusive.
- Live Gemini pending classifications: 26 classified, 0 errors, all remain unapproved.
- SQL parser accepted 49 statements across the two migration files; actual migration
  execution and ledger verification also passed.

Raw verification reports: product/output/api_validation.json,
product/output/database_validation.json, and the fresh run's phase2_run_report.json.
Run read-only API verification again with `python -m product.verify_api` while the
API is running. Database integration tests are opt-in and use explicit test URLs;
the Phase 1 test requires an empty app/meta schema and must not be run against the
now-populated project. Phase 2 test wraps its writes in rollback transactions.

## Next phase and remaining boundaries

Phase 3: build the actual `/`, `/jobs` and search/filter/mobile experience against
this API. Phase 4: details UI and source Apply click/redirect flow. Phase 5: managed
auth, saves and tracker. Pending new-source reviews can be completed independently.

Before public launch: validate source attribution links in the UI; implement
scheduled refresh and the downstream export consumer; production auth/mail delivery;
user-data policies; rate limiting; backups/restore and deployment smoke tests.
The current API is local and does not constitute a publicly deployed job platform.

Official references used for implementation:

- https://nextjs.org/docs/app/getting-started/route-handlers
- https://node-postgres.com/features/ssl
- https://supabase.com/docs/guides/database/postgres/row-level-security
- https://supabase.com/docs/guides/platform/ssl-enforcement
- https://remoteok.com/api
