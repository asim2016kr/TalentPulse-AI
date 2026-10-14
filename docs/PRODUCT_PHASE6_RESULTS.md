# Phase 6 — hardening and release verification

Verified locally on 14 October 2026. The implementation and no-email QA are complete.
Public launch remains gated by the explicitly untested items below.

## Changes

- Per-request cryptographic script nonces, strict script policy, same-origin form
  and network restrictions, and dynamic rendering across application pages.
  Inline style attributes remain allowed for React; arbitrary inline scripts do not.
  Implementation follows [Next.js CSP guidance](https://nextjs.org/docs/app/guides/content-security-policy).
- Account throttling responses now include Retry-After. Unexpected API failures
  emit only a correlation ID, without SQL, tokens, driver messages or personal data.
- Sign-out has a bounded timeout and prevents repeat submissions.
- Fresh hosted CI exposed an incompatible optional Snowflake pandas/Arrow extra.
  Removed that unused extra and pinned the existing connector version; warehouse
  access uses cursor rows/executemany and retains its existing functionality.
- Added liveness and production configuration checks, CI, and repository credential
  and generated-artifact checks. Existing readiness check validates the read database.
- Preserved all previous product and Python pipeline work in the GitHub source
  snapshot. Removed generated CSVs/charts from the current Git index; local files
  remain intact. Historical commits are unchanged.
- Private raw snapshots, classification evidence, runtime reports, credentials and
  dependencies are excluded. Archive-dependent tests explicitly skip without their
  original local evidence; they are never silently replaced with fabricated data.

## Evidence

| Check | Result |
|---|---|
| Production Next.js build and TypeScript | Passed |
| Web unit tests | 21 passed |
| Local Python regression suite | 73 run, 71 passed, 2 opt-in database tests skipped |
| Exported Git source without local archives | 66 run, 7 skip events, no failures (includes skipped seed class) |
| Live restricted-role account integration | 11 checks passed; two synthetic app users cleaned up |
| Jobs HTTP | 29 passed; 23 fresh public jobs |
| External-apply HTTP | 10 passed; zero guest writes |
| Auth HTTP boundaries | 15 passed; zero emails |
| Production security HTTP | 8 passed, including distinct nonces matching every script on auth/jobs/404 pages |
| npm production dependency audit | Zero reported vulnerabilities |
| Repository scan | No staged matches for local API keys/passwords; artifact/pattern checks passed |

Browser verification: production-build password visibility toggle, client navigation
to jobs and details, guest Save returning to sign-in with the original job preserved,
and mobile sign-in layout at 390px. No console errors observed in this journey.
This verifies hydration under CSP; it does not substitute for an authenticated journey.

`npm run preflight` correctly rejects the current local development environment:
it has an HTTP URL, development cookies and shared owner/worker/AI configuration.
No production environment was provisioned or modified in this phase.

## Explicit launch gates

1. Verify signup confirmation, successful sign-in, session refresh, password recovery,
   sign-out and signed-in saves/application tracking end to end with a controlled
   account. No emails were sent, as requested. Database service tests cover personal
   data behavior but do not prove the complete Supabase/browser cookie journey.
2. Configure a public HTTPS domain, Supabase callback allowlist and SMTP sender;
   separate web secrets from ingestion/migration credentials; pass preflight.
3. Configure deployment-side request/body limits, per-client abuse protection,
   uptime/error alerts, backups and a restore drill. Application-level global
   throttles are bounded MVP safeguards, not a replacement for edge controls.
4. Refresh/review source listings before release and schedule operational refreshes.
   Pending classifications remain unpublished. Freshness can hide stale jobs.

See [release runbook](RELEASE_RUNBOOK.md). Phase 7 is deployment and launch.
