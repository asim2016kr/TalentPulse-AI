# TalentPulse release runbook

## Reproduce checks

Use Node 24 and Python 3.14. From the repository root:

```powershell
python -m pip install -r requirements.txt -r product/requirements.txt
python -m unittest discover -s tests -v
python scripts/check_repository.py
cd web
npm ci
npm test
npm run build
npm audit --omit=dev --audit-level=high
npm start
```

The local launcher binds only 127.0.0.1:3000. It loads the private root .env.
On a hosting platform, run Next directly with its platform PORT/HOST binding and
explicit environment variables. Do not copy the shared development .env to hosting.

Against the running local production build, from the root:

```powershell
python -m product.verify_api
python -m product.verify_apply
python -m product.verify_auth
python -m product.verify_security
cd web
node --conditions=react-server --import tsx scripts/verify-accounts.ts
```

The last script explicitly creates and cleans up two temporary **app** users;
it needs the local owner connection. It creates no Supabase Auth users and sends
no email. Do not run the empty-database initialization test against this database.
Private archive tests need the existing local snapshots; a fresh clone reports
those skips. Use capture/review ingestion for new data rather than treating old
development seeds as fresh listings.

## Production configuration

Web environment only: APP_ENV=production, APP_BASE_URL=https://your-domain,
ALLOW_DEVELOPMENT_JOBS=false, APP_DATABASE_URL, MEMBER_DATABASE_URL,
DATABASE_CA_CERT, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY. Supply the CA file at
the configured path relative to the repository root (or an absolute path).
Never expose database URLs or API keys through NEXT_PUBLIC variables.

Run `npm run preflight` from web in the production configuration. It rejects
development settings and owner/worker/AI credentials in the web environment,
then checks restricted database roles. Migrations run as a separate release job;
review SQL and verify backup availability before applying them.

Configure Supabase's Site URL and exact HTTPS `/auth/callback` redirect allowlist,
email confirmation and custom SMTP. Complete the manual account journey in the
Phase 6 report only when email testing is authorized. Test two accounts for
isolation, expiry/refresh, recovery, logout, saved jobs and idempotent apply clicks.

## Operations and rollback

- `/api/health`: process liveness; `/api/v1/health`: read-database readiness.
  Neither confirms email delivery or worker freshness. Alert on sustained failures
  and collect sanitized `api_failure` IDs. Do not log request bodies/cookies.
- Put public endpoints behind platform request size/time limits and per-client
  throttles. Verify trusted proxy handling before using forwarded client IPs.
- Monitor fresh-listing count, last successful ingestion run and review backlog.
  Run the existing capture → classify/review → check-links → plan → apply workflow
  from the Phase 2 runbook with worker credentials outside the web service.
- Take and verify encrypted database backups with retention and access controls.
  Restore into an isolated database, validate schema/row counts/RLS, and document
  recovery time before launch. No backup/restore success is claimed by local QA.
- Record the deployed commit and migration ledger. Roll back the web deployment
  to its previous tested artifact for application regressions. Do not reset or
  reverse applied migrations blindly; use a reviewed forward fix or tested restore.
- Keep a launch checklist with owner, date and evidence for each open gate. Release
  only after hosted CI, production preflight and the manual account journey pass.
