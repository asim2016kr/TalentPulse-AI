# TalentPulse — Phase 1: product and data foundation

Decision date: 2026-09-21. Scope: a job discovery and external-apply MVP.
This replaces the analytics-first product direction, not the existing ingestion work.
Phase 1 delivers database/migration/seed code and API/page contracts; it does not
implement the website, authentication endpoints or production ingestion scheduler.

## 1. Product scope and stack

Users browse/search without an account, open a complete job description, and leave
TalentPulse to apply. Accounts unlock saved jobs and a self-reported application
tracker. No employer accounts, uploaded resumes, internal submissions, payments,
recommendation engine, salary comparisons or conversational assistant are required
for launch. Initial supply remains reviewed technology jobs; other sectors require
a later taxonomy/data decision.

Recommended stack:

- Next.js with TypeScript/React, App Router pages and server Route Handlers for
  `/api/v1/*`. One web deployment, not a separate Python HTTP microservice.
- Supabase-hosted PostgreSQL for application data and Supabase Auth for password
  hashing, email verification, recovery and session/token lifecycle.
- SQL migrations are the canonical schema; Python uses psycopg 3. The Next.js
  backend will use parameterized PostgreSQL queries. No ORM or Elasticsearch is
  needed for this MVP. PostgreSQL full-text search and B-tree/GIN indexes suffice.
- Existing Python ingestion, cleaning, Gemini classification and explicit review
  remain backend jobs, independent of user HTTP requests.
- Snowflake is downstream analytics only. No job page, login, save or apply flow
  depends on Snowflake. The old dashboard stays a separate internal prototype.

```mermaid
flowchart TD
  Source[Job source APIs] --> Raw[Immutable raw snapshot]
  Raw --> Pipeline[Existing Python clean / classify / review]
  Pipeline --> Gate[Quality and freshness gate]
  Gate --> PG[(PostgreSQL application data)]
  Auth[Supabase Auth] --> Server[Next.js server API]
  PG <--> Server
  Server <--> UI[React job browsing website]
  UI --> External[Source or employer application website]
  PG --> Export[Scheduled validated analytics export]
  Export --> SF[(Snowflake)]
```

## 2. Schema and ownership

Canonical DDL: `product/migrations/001_initial.sql`, PostgreSQL 15+.
All IDs are UUIDs; timestamps are timezone-aware and returned as UTC ISO 8601.
Private `app` schema must not be added to Supabase's exposed Data API schemas.

| Table | Purpose and invariants |
|---|---|
| `users` | UUID equals verified Supabase subject; email (case-insensitive unique), display name, verification/sign-in/disable timestamps and audit timestamps. Auth provider is authoritative for identity. |
| `companies` | Source-scoped identity key, name, nullable domain/website, basic JSON metadata. Never infer a domain from a company name or logo URL. |
| `jobs` | Company, full plain-text source description, title, classification, source tags, location/work type, source ID/URL, external application URL and destination kind, source hash, ingestion run, publication/observation/freshness timestamps, status and development flag. |
| `saved_jobs` | Composite key `(user_id, job_id)` prevents duplicate bookmarks. |
| `applications` | One tracker per user/job; separate click timestamps, self-reported status and applied timestamp. |
| `application_clicks` | Append-only signed-in click events with unique `(user_id, request_id)` for safe retries. No resume/application contents stored. |
| `ingestion_runs` | Source/archive/review hashes, observation timestamp, fixture flag and imported count, for reconciliation and traceability. |

Authentication fields deliberately span the managed auth store and `app.users`:
**password hash, refresh tokens, verification tokens and recovery secrets live in
Supabase Auth only**. They are never duplicated in the application schema. Provision
an app user on the server after verifying an Auth response/session, using its subject
and verified email. Auth signup may succeed before this upsert; retry the upsert on
the next login. Do not trust user metadata for identity, verification or privileges.
Auth deletion plus application-data deletion is an explicit backend operation;
the provider-neutral schema does not silently assume a local `auth.users` FK.

`classification` preserves the original prediction/model/provider/version and the
subsequent reviewed labels/evidence. Review in the current fixture was performed by
the Codex assistant, not an independent human. Original confidence is not a calibrated
confidence for corrected labels. `source_tags` remain noisy source metadata and must
not be labelled verified required skills. No salary display is included because the
source lacks consistently verified currency/pay period.

Company identity currently falls back to `remoteok:name:<normalized name>` within
one source. This can conflate same-name companies or split renamed companies; preserve
provenance and add reviewed aliases when introducing another source. Job deduplication
is exact `(source, source_job_id)`, with stable UUIDs across imports. Cross-source
fuzzy deduplication is not part of this seed.

### Publication and freshness

- `unverified`: imported but eligibility/availability has not been established; not
  part of public search. All development fixtures remain here.
- `active`: explicitly passed source, description, link and recency checks. Requires
  `freshness_checked_at` and `fresh_until`; never inferred from import time.
- `expired`: confirmed source closure or source expiry, retained for saved/history
  records with Apply disabled. Do not hard-delete jobs referenced by users.
- Public visibility requires `status='active' AND NOT is_development AND
  fresh_until > now() AND (expires_at IS NULL OR expires_at > now())`. This predicate
  must also gate direct detail access and apply eligibility, not just search.
- Stale active rows become unavailable immediately via that predicate, even if a
  scheduler is late. Phase 2 will use a configurable 7-day recheck window as an MVP
  policy, not a claim about the employer's closing date.
- A job missing from a limited/paginated feed is not proof it expired. Rate limits,
  source failures and incomplete runs never mass-expire the database.
- Historical fixtures are visible only in an explicit development preview on the
  backend (`APP_ENV=development`, `ALLOW_DEVELOPMENT_JOBS=true`). Public production
  must refuse that flag. Preview labels say development data; Apply remains disabled.

### Security boundary

The initial migration revokes public access and enables RLS with no permissive
policies: it is closed by default. Migration/seed commands use the owner connection;
**that credential must not be used by the web runtime**. Runtime role/policy setup is
a required Phase 2 deliverable before public deployment, not implemented here.

Runtime plan: a non-owner `talentpulse_web` role, no DDL/ingestion access; SELECT
companies/eligible jobs, own-row access to users/saves/applications/clicks. Set a
transaction-local user UUID only after server session verification, enforce owner
predicates and RLS, and use a separate ingestion role for company/job upserts.
Restrict user profile updates to display name; identity fields are synced through a
trusted server procedure. Saved/history joins may show minimal expired job metadata
only for the owning user; unverified development rows never leak into production.
Add role-specific integration tests before enabling these grants. No anonymous
Supabase Data API access to these tables is needed.

Backend validates sessions against Supabase, checks account disable/verification,
uses parameterized queries, and uses secure HttpOnly SameSite cookies in production.
Mutation endpoints require same-origin/CSRF checks; no permissive CORS. Do not log
passwords, cookies, tokens or connection URLs. Add auth/apply rate limits, request
body limits and generic login errors when implementing handlers. API keys and the
ingestion pipeline are never bundled into React. Job descriptions are rendered as
text; the source HTML remains in the backend archive, not injected into the DOM.

## 3. REST contract

Base path `/api/v1`. JSON uses snake_case. UUID route IDs only. All dates UTC.
Success returns `{ "data": ... }`, lists also return `pagination`. Errors return
`{ "error": { "code": "...", "message": "...", "request_id": "..." } }`.
Use 400 malformed input, 401 missing/invalid session, 403 unverified/disabled account
or CSRF denial, 404 inaccessible/missing record, 409 idempotency conflict,
410 unavailable application destination, 422 field validation, 429 rate limit and
503 upstream/database outage. Never return SQL/provider secrets or raw exceptions.
Authentication, personal lists and mutation responses use `Cache-Control: no-store`.

### Authentication routes (server adapters around Supabase Auth)

| Method / route | Request | Successful response |
|---|---|---|
| POST `/auth/signup` | `{"email":"user@example.com","password":"...","display_name":"Asim"}` | 202 `{"data":{"message":"Check your email to continue"}}`; generic response also avoids account enumeration. |
| POST `/auth/login` | `{"email":"user@example.com","password":"..."}` | 200 `{"data":{"user":{"id":"<uuid>","email":"user@example.com","display_name":"Asim"}}}` and secure session cookies. |
| POST `/auth/logout` | `{}` | 204, revoke session as supported and clear cookies. |
| GET `/auth/me` | Cookie session | 200 `{"data":{"id":"<uuid>","email":"user@example.com","display_name":"Asim","email_verified":true}}`; 401 otherwise. |
| POST `/auth/forgot-password` | `{"email":"user@example.com"}` | 202 generic email-sent message, including unknown accounts. |
| POST `/auth/reset-password` | `{"password":"..."}` and valid recovery session | 204. |

Password minimum 12 characters for the MVP; enforce the provider's accepted maximum
without truncation. Display name 1–100 characters, trim emails/names, never trim
passwords. Configure provider email confirmation. Implement server session refresh
through the supported Supabase SSR flow; do not invent local JWT signing/password
storage. The auth callback exchanges/verifies provider codes and redirects only to
allowlisted local relative paths. Never return refresh tokens in JSON/localStorage.

### Job routes

`GET /jobs?q=data%20engineer&role=Data%20Engineer&work_mode=Remote&experience_level=Senior&location=India&company_id=<uuid>&source_tag=python&page=1&page_size=20&sort=newest`

- All filters optional. `q` max 200 characters, location max 100, page >=1,
  page_size 1–50 default 20; reject offset beyond 10,000 for this MVP.
- Role/category/experience/work-mode/job-type values use a server allowlist from the
  classification contract. Include category and job_type filters as well.
- Keyword search uses `websearch_to_tsquery('english', q)` against the indexed
  title/description and a parameterized escaped company-name match. Location is a
  literal case-insensitive substring of unstandardized source text. Unknown is not
  treated as worldwide/remote. Source-tag matching is case-insensitive exact match.
- Sort `newest` default: published_at DESC NULLS LAST, id DESC. `relevance` needs
  nonempty q: text rank DESC, published_at DESC NULLS LAST, id DESC. Identical sort
  ties use UUID for deterministic order; offset pages may shift when data updates.
- Count and rows use the exact same eligibility/filter predicate, in a consistent
  read transaction. Empty search returns `data:[]`, total 0. No query parameters
  can enable unverified fixtures in production.

```json
{
  "data": [{
    "id": "<uuid>", "title": "Data Engineer",
    "company": {"id":"<uuid>","name":"Example","domain":null},
    "location_text": "India", "work_mode": "Remote", "job_type": "Unknown",
    "role": "Data Engineer", "category": "Data Engineering", "experience_level":"Senior",
    "source_tags": ["python"], "published_at":"2026-09-21T08:00:00Z",
    "status":"active", "freshness_checked_at":"2026-09-21T09:00:00Z",
    "source": {"name":"Remote OK","url":"https://remoteok.com/remote-jobs/example"}
  }],
  "pagination": {"page":1,"page_size":20,"total":1,"total_pages":1}
}
```

This is a contract example, not an actual active listing.

`GET /jobs/:id` returns the same summary inside `data`, plus `description_text`,
`application_url_kind`, `can_apply`, `availability_message`, `fresh_until`,
`expires_at` and `updated_at`. No review internals, raw source payloads or user data.
Expired/stale formerly published details may return 200 with `can_apply:false` and
an availability explanation; unverified/nonpublic IDs return 404. These detail
exceptions need a deliberate backend policy; never reuse a wide-open SELECT.

`GET /jobs/filters` returns `{"data":{"roles":[],"categories":[],"work_modes":[],
"experience_levels":[],"job_types":[]}}` populated from eligible listings. No
skills-in-demand or other analytics endpoint is part of the job-board MVP.

### Save, apply and track routes

| Method / route | Auth / input | Successful response |
|---|---|---|
| PUT `/me/saved-jobs/:job_id` | Verified user, `{}` | 200 `{"data":{"job_id":"<uuid>","saved":true}}`; idempotent. New saves require eligible job. |
| DELETE `/me/saved-jobs/:job_id` | Verified user | 204, including already absent save. |
| GET `/me/saved-jobs?page=1&page_size=20` | Verified user | 200 list `{job:<summary>,saved_at:<timestamp>,can_apply:<bool>}` with standard pagination; retain expired entries with a label. |
| POST `/jobs/:id/apply-click` | Optional session, `{"request_id":"<uuid>"}` | 200 `{"data":{"redirect_url":"https://remoteok.com/remote-jobs/...","destination_kind":"source_listing","tracked":true,"application_status":"clicked"}}`. Guest: tracked false and application_status null. |
| PUT `/me/applications/:job_id` | Verified user, `{"status":"applied"}` | 200 `{"data":<Application>}`; may create a tracker without a prior click. |
| GET `/me/applications?page=1&page_size=20&status=applied` | Verified user | 200 list of Application + job summary and standard pagination. |

Application response:
```json
{"id":"<uuid>","job_id":"<uuid>","status":"applied",
 "first_clicked_at":"2026-09-21T09:00:00Z","last_clicked_at":"2026-09-21T09:00:00Z",
 "self_reported_applied_at":"2026-09-21T09:10:00Z",
 "status_updated_at":"2026-09-21T09:10:00Z","updated_at":"2026-09-21T09:10:00Z"}
```

Status updates accept `applied`, `interviewing`, `offer`, `rejected`, `withdrawn`.
`clicked` is set only by the click endpoint for a newly created tracker. Existing
self-reported statuses never revert to clicked on another redirect. Set the applied
timestamp on first explicit `applied` report; do not invent it for interviewing/offer.
Status changes are user-reported, not verified employer events. Editing the same
status twice is a no-op; changed status updates status_updated_at. Permit updates to
existing trackers for expired listings; new trackers require a visible listing.

Signed-in click processing is one transaction: recheck job eligibility; insert
`application_clicks` with idempotency key; create/update first/last click timestamps
in applications only if the event is new; commit before returning the URL. Reusing
a key for another job is 409. Repeated same-key requests do not add another event.
Guest clicks return the link without creating personal records. A supplied invalid
session is 401, not silently treated as guest. On a tracking/database failure return
503, not a false success. The frontend performs the external navigation after success.

Never accept a redirect URL from the caller. Resolve it from the stored source
adapter's validated URL, require HTTPS and approved source/employer hosts, reject
credentials/private hosts/malformed schemes, and recheck eligibility. Phase 1 seed
allows only Remote OK listing URLs; source pages may redirect onward independently.
No server-side fetching of arbitrary URLs in request handlers. Link checks in the
ingestion worker require SSRF-safe DNS/IP and redirect validation when implemented.

## 4. Frontend routes and exact MVP flows (design only)

| URL | Components and behavior |
|---|---|
| `/` | Product header, keyword/location search, latest eligible job cards, sign-in link. Search navigates to `/jobs?...`. |
| `/jobs` | Search form, filter controls, result count, job-card list, pagination, loading/empty/error states. Query string preserves search state. |
| `/jobs/:id` | Title/company/location, full description, source attribution, last-check status, Save and external Apply buttons. Unavailable jobs explain why Apply is disabled. |
| `/signup?next=/jobs/:id` | Email/password/name form and confirmation state. |
| `/login?next=/jobs/:id` | Login form, recovery/signup links. Only allowlisted local next URLs. |
| `/auth/callback` | Server-only provider callback; no product page. |
| `/forgot-password` | Recovery request form, generic confirmation. |
| `/reset-password` | New password form after provider recovery validation. |
| `/dashboard` | Protected account summary with Saved Jobs and Applications tabs. |
| `/dashboard/saved` | Saved cards, remove action, expired state. |
| `/dashboard/applications` | Tracked jobs, external click vs self-reported status, status selector. |

Browse/detail/apply are anonymous. Save while logged out redirects to login with a
safe return path; after login return to the job and let the user confirm Save (do
not perform hidden state changes through a GET callback). Logged-in Apply records
the redirect, opens the source page, and allows later confirmation on the tracker.
Never display 'Application submitted' merely because the user clicked Apply.
No employer portal, resume page, inbox, AI assistant page or analytics-first landing
page is included. The old website is not replaced during Phase 1.

## 5. Data integration and migration path

Current pipeline artifacts remain immutable inputs. Do not build product listings
from Snowflake fact tables: those omit descriptions and are shaped for analytics.

1. Preserve the raw source snapshot, collection timestamp, source attribution and
   terms metadata for every run. Existing archive includes descriptions/apply URLs.
2. Run existing cleaning/classification/review gates; quarantine ambiguity and keep
   original predictions. The seed reuses the existing pure-Python preflight validator
   from `warehouse.reload_validation`; it does not open a Snowflake connection.
3. Join approved transformed records to archived raw records by source ID, verify
   archive hash against review evidence, strip unsafe HTML to plain text, and retain
   URL kind/provenance. Unknown locations/domains stay unknown.
4. Production adapter in Phase 2 verifies eligible descriptions, provider rights,
   freshness and external destinations, then transactionally upserts companies/jobs.
   Preserve UUIDs, first_seen_at, bookmarks and trackers. No full-table replacement.
5. Use source/content hashes for retries; reconcile counts and reject stale overwrites.
   If descriptions change, invalidate prior review/classification as appropriate:
   today's classification cache uses title/tags, so it is not a full-description
   freshness/review guarantee. Re-review changed job content before publication.
6. After a successful application commit, independently export a consistent reviewed
   snapshot to Snowflake. Use a durable run/export checkpoint; analytics failures
   retry downstream and cannot roll back user-facing job availability. No dual writes
   from individual user requests and no default export of user email/password data.

### Existing 32-job seed

`python -m product.seed_snapshot` validates the transformed CSV manifest, re-runs
review gating, checks archived source SHA against every reviewed row, rejects missing
or duplicate source IDs and unsafe links, and prepares 32 records for 30 companies.
Full descriptions exist for all 32. The source application URLs are Remote OK pages,
not verified direct employer forms. Source observed-at remains September 15, 2026;
importing today never changes it to today.

`--export product/output/development_seed.json` writes a development fixture for
later UI work without a database. `--apply` imports in one transaction using
`APP_ENV=development`. Re-runs keep job UUIDs and user references. The importer
refuses to overwrite newer or non-development jobs. Its job count is intentionally
locked to 32: use the Phase 2 generalized production adapter for future snapshots.
Development records cannot be active by a database CHECK constraint. To publish
later, a fresh production ingestion/review must explicitly replace the development
designation and satisfy the freshness gate; no bulk 'make active' shortcut.

Remote OK's current API metadata asks for source attribution and a follow link back
to the source job. Each job detail must preserve that attribution/link. This is not
a blanket legal clearance for all sources or permanent terms: review and archive
source terms before public release and honor removal requests.

## 6. Free-tier services and configuration

Verified against official pages on 2026-09-21; quotas can change.

| Service | Role / current free offering | Configuration |
|---|---|---|
| Supabase | PostgreSQL + Auth: 500 MB DB, 50,000 monthly active users, 5 GB egress; 2 active free projects, inactivity pause after a week, no automatic backups on Free. Appropriate for development/initial MVP, not an uptime commitment. | Create free project; copy Connect connection string and project URL/publishable key. |
| Gemini Developer API | Existing classifier; model-dependent free quota and rate limits. Keep current configured model if available to this account. Job browsing does not call Gemini. | Existing GEMINI_API_KEY and GEMINI_MODEL; no OpenAI key needed. |
| Remote OK API | Existing no-key source endpoint; attribution obligations apply. Coverage and live-link quality still need Phase 2 validation. | No new API key. |

Recommended: one Supabase project for development now. No paid service, new account
or credentials were created by this implementation. A Supabase API publishable key
is not a database password, and the database URL is not an API key.

Add these values **only to `C:\TalentPulse-AI\.env`** (template in `.env.example`):

```dotenv
APP_ENV=development
DATABASE_URL=postgresql://USER:YOUR_URL_ENCODED_PASSWORD@HOST:5432/postgres?sslmode=require
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
APP_BASE_URL=http://localhost:3000
ALLOW_DEVELOPMENT_JOBS=false
```

Get DATABASE_URL from Supabase project → Connect → **Session pooler** (use the
actual supplied username/host; this supports IPv4). URL-encode special password
characters. Use the owner connection only for migrations/seed. Phase 2 will add
`APP_DATABASE_URL` for a restricted web role. Get SUPABASE_URL and publishable key
from the project's API settings/Connect panel. A secret/service-role key is not
required for Phase 1; do not add one to the browser. Do not paste any key into chat.
Keep existing Gemini/Snowflake entries intact. No `NEXT_PUBLIC_` secrets.

In the later Next.js application, its deployment/server environment must receive
the required variables explicitly; do not assume Next loads the repository's parent
`.env`. The root `.env` is for Python. Configure Auth Site URL and callback/reset
redirect allowlists for local and production origins when implementing authentication.

Signup email delivery is a separate launch dependency: Supabase's default mail
service is restricted and low-rate (documented 2 emails/hour), so configure a custom
SMTP provider and verify sender/domain before opening public signups. Do not disable
email confirmation as a substitute. SMTP setup belongs in Supabase's Auth settings,
not React. Select and verify a mail provider's current free quota in Phase 5.

### Commands (PowerShell, from C:\TalentPulse-AI)

```powershell
.\venv\Scripts\python.exe -m pip install -r product\requirements.txt
.\venv\Scripts\python.exe -m product.migrate
.\venv\Scripts\python.exe -m product.seed_snapshot --export product\output\development_seed.json
# After configuring the development database:
.\venv\Scripts\python.exe -m product.migrate --apply
.\venv\Scripts\python.exe -m product.seed_snapshot --apply
.\venv\Scripts\python.exe -m unittest discover -s tests
```

Migrations use an advisory lock and checksum ledger and are transactional. Applied
migrations must not be edited; append new numbered migrations. No destructive down
or database reset command is provided. The seed does not delete existing listings.
Back up the development database before manual destructive experiments; arrange
scheduled encrypted backups/restore testing before launch because Free lacks them.

## 7. Acceptance and execution boundaries

Phase 1 code must pass offline regression and seed-gate tests. A configured disposable
PostgreSQL instance is still required to verify actual migration application, repeat
imports, FK/check constraints and rollback. No configured database means these checks
are pending, not passed. Full auth/API behavior is a future implementation contract.

Phase 2: provision runtime roles/RLS; verify real PostgreSQL migrations/seed; implement
production adapter and source checks; implement job read APIs. Phase 3 builds the
search UI against these contracts. Phase 4 delivers details/external apply. Phase 5
adds managed auth/saves/tracker. Phase 6 hardens complete flows; Phase 7 deploys.
No UI or existing Snowflake data is modified as part of this phase.

## Official references

- Supabase pricing: https://supabase.com/pricing
- Database connection modes: https://supabase.com/docs/guides/database/connecting-to-postgres
- Password auth/email limitations: https://supabase.com/docs/guides/auth/passwords
- Remote OK API/attribution metadata: https://remoteok.com/api
- Gemini API model pricing/free tiers: https://ai.google.dev/gemini-api/docs/pricing
