# Product Phase 5 — Accounts, shortlist and application workspace

Implementation date: 13 October 2026. The existing Next.js, PostgreSQL, Python ingestion and downstream Snowflake architecture is retained.

## Delivered product behavior

- `/signup`, `/login`, `/forgot-password`, `/reset-password`: responsive account forms, password visibility, input validation, pending states and clear error/success messages. Existing sage/charcoal visual design carries through the account experience.
- `/auth/callback`: Supabase PKCE code exchange, approved local return paths, private/no-store responses, and safe failure navigation. Development callbacks preserve the browser's localhost or 127.0.0.1 host instead of redirecting between cookie domains.
- Job details include Save/Remove, with login return to the selected job. Failed saved-state loads offer retry instead of silently claiming an unsaved state.
- `/dashboard/saved`: personal shortlist, unavailable-listing labels, removal, marking a saved eligible job as applied, pagination, meaningful empty state and sign-out.
- `/dashboard/applications`: opened-site versus self-reported application status, status editing, applied timestamp and unavailable historical listings. Statuses: applied, interviewing, offer, rejected and withdrawn.
- Signed-in external apply records an idempotent click before returning the approved URL. Retrying the same request does not duplicate an event; reusing a key for another job fails. Opening the source again never resets a self-reported application status to clicked. Guests remain untracked.

## Authentication and data boundaries

Supabase Auth owns passwords, verification and recovery. No local password storage or custom JWT scheme was introduced. `@supabase/ssr` runs on the server, uses HttpOnly/SameSite=Lax cookies, and refreshes through Next.js proxy. Cookies use Secure outside explicit development mode. Credentials/tokens are not exposed through JSON or browser localStorage. Protected server handlers independently call `auth.getUser()` and require a confirmed email. User metadata is display-only; identity and verification come from the verified provider record.

Migration `003_personal_accounts.sql` creates a dedicated `talentpulse_member` role. The generated `MEMBER_DATABASE_URL` is saved only in the root `.env`. Public reads still use their separate read-only login. Personal transactions set a verified user UUID transaction-locally; RLS prevents cross-user access and blocks disabled accounts. The runtime cannot change account disable flags or read internal classification evidence. New bookmarks/trackers require an eligible listing. Existing trackers remain editable when jobs expire; hidden jobs show an unavailable placeholder.

Mutations require an approved Origin, JSON content type and bounded bodies. Post-login navigation uses an explicit local-path allowlist. Forged/expired sessions fail closed rather than becoming anonymous apply requests. Shared PostgreSQL rate limits cover authentication and account actions. The rate table contains hashes, not raw email/IP identifiers. These limits complement, rather than replace, deployment abuse protection.

Security headers block framing, restrict base/object embedding and disable unused camera/microphone/geolocation features. Private responses are not cacheable. A strict nonce-based script CSP, operational monitoring and edge-level abuse controls remain Phase 6/7 work.

## API additions

- `GET /api/v1/auth/me`
- `POST /api/v1/auth/{signup,login,logout,forgot-password,reset-password}`
- `GET /api/v1/me/saved-jobs[?page=1]`
- `GET /api/v1/me/saved-jobs/:job_id` (saved-state lookup)
- `PUT /api/v1/me/saved-jobs/:job_id` with `{}`
- `DELETE /api/v1/me/saved-jobs/:job_id` with `{}`
- `GET /api/v1/me/applications[?page=1&status=applied]`
- `PUT /api/v1/me/applications/:job_id` with `{"status":"applied"}`
- Existing `POST /api/v1/jobs/:id/apply-click` now supports verified sessions and persistent idempotency.

Auth input uses email/password, plus display_name for signup and an optional allowlisted next path. Password creation/reset accepts 12–128 characters without trimming. Lists return data plus pagination; errors use status/code/message/request_id. Identity is never accepted from a request body.

## Verification completed

- Production Next.js build and TypeScript compilation passed.
- 18 web tests passed, covering input boundaries, trusted origins, callback/return redirects, destination validation, failure handling and existing search behavior.
- Eleven live account-service/database integration checks passed: save idempotency, cross-user isolation, forged owner denial, protected columns, transaction-local pool identity, concurrent click retries, cross-job idempotency conflicts, preserved statuses/timestamps, tracker isolation, bookmark removal and disabled-account RLS.
- Integration fixtures were two synthetic `app.users` rows, removed in cleanup with their child records. No Supabase Auth accounts were created and no emails were sent.
- Fifteen live auth HTTP boundary checks passed: unauthenticated denial, forged-cookie denial, cross-site rejection, invalid login, validation-before-signup, unauthenticated reset rejection, callback safety and account page/cache/security headers.
- Existing 29 job API and 10 guest-apply checks passed. Python regression suite: 73 discovered, 71 passed, two opt-in database checks skipped.
- Supabase public settings confirmed email auth enabled, signup enabled and email confirmation required. This does not establish SMTP readiness.
- Browser review covered desktop/mobile account forms, password visibility, recovery navigation, guest workspace protection and guest Save returning to the correct job after sign-in. No horizontal overflow was found at the tested mobile viewport. No signup/recovery email form was submitted, following the user's instruction.

## Explicit production release gates

This phase implements the account features; it is not a claim that the application is ready for public production traffic.

1. Configure/verify custom SMTP and sender domain in Supabase Auth. The default Supabase mail service is intended for non-production use and restricts recipients; do not disable email confirmation to work around delivery.
2. Configure Auth Site URL and redirect allowlist. For local testing, allow callback paths on both `http://127.0.0.1:3000` and `http://localhost:3000`, including the application-generated next query. For production, use the final HTTPS domain only. Keep PKCE callback links in the browser where the request began.
3. Set `APP_ENV=production`, `APP_BASE_URL=https://<final-domain>` and securely supply existing server credentials on deployment. Keep private app schemas outside the Supabase Data API. No service-role key is required for this implementation.
4. Run a real confirmation/login/refresh/recovery/logout round trip and signed-in browser save/tracker journey with a controlled account. These were deliberately not exercised through email. The signed-in services and database were tested directly; authenticated browser behavior remains a verification gap.
5. Complete Phase 6/7: abuse controls, full accessibility/interaction QA, backup/restore readiness, operational monitoring, deployment and source refresh/review operations.

No user email was requested again after the user chose testing without emails. SMTP and successful email round-trip verification remain pending, not silently marked passed.

## Reproduce checks

From `C:\TalentPulse-AI\web`: `npm test`, `npm run build`, `npm run start`.
Account service integration: `node --conditions=react-server --import tsx scripts/verify-accounts.ts` (uses existing configured database; only its generated synthetic app users are cleaned up).
From the repository root: `python -m product.verify_auth`, `python -m product.verify_api`, `python -m product.verify_apply` using the project virtual environment and running local web server.

## Official references checked

- [Supabase server-side client and proxy guidance](https://supabase.com/docs/guides/auth/server-side/creating-a-client)
- [Supabase advanced server-side auth guidance](https://supabase.com/docs/guides/auth/server-side/advanced-guide)
- [Supabase SMTP production requirements](https://supabase.com/docs/guides/auth/auth-smtp)
- [Supabase production checklist](https://supabase.com/docs/guides/deployment/going-into-prod)
