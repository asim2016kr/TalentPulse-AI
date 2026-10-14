# Product Phase 4 — Details and external apply

Completed 12 October 2026 on the existing Next.js/PostgreSQL architecture.

## User flow

Browse `/jobs`, open `/jobs/:id`, read the supplied description and source information, then choose **Apply on Remote OK**. The button displays a pending state while the server checks current database eligibility. On success the browser navigates to the matching Remote OK listing in the same tab. The user completes the application on the external site. Browser Back returns to the TalentPulse listing.

Unavailable listings disable Apply and offer a route back to job search. A listing that becomes unavailable after the page loads is rejected by the click endpoint. Transient failures show an inline retry message; there is no unchecked redirect fallback. Clicking does not submit an application or create a personal tracker.

Descriptions are escaped plain text and may be provider excerpts; the page explains that limitation. Source tags are explicitly labelled provider metadata, not verified required skills. Source attribution remains a separate link.

## API

`POST /api/v1/jobs/:id/apply-click`

Request: `Content-Type: application/json`, trusted `Origin`, body `{"request_id":"<uuid>"}`. No query parameters or destination URL accepted. Browser calls use the same origin.

Success: `{"data":{"redirect_url":"https://remoteok.com/remote-jobs/<listing>","destination_kind":"source_listing","tracked":false,"application_status":null}}`.

- UUID, JSON shape and 1 KiB body bound checked before querying PostgreSQL.
- Origins come from backend `APP_BASE_URL`; development also permits localhost and 127.0.0.1 on port 3000. No arbitrary reflected Origin or forwarded-IP trust.
- Existing restricted read role resolves the destination from the stored record. The active/nondevelopment/freshness/expiry predicate is evaluated again on each request, including repeated guest requests.
- Approved source/kind, HTTPS, exact `remoteok.com` host and listing path required. Credentials, nonstandard ports, query strings, fragments, private hosts and malformed URLs are rejected. No external HTTP fetch is performed by this endpoint.
- 400 invalid input; 401 supplied unsupported account session; 403 origin denied; 404 hidden/missing job; 410 unavailable or unsafe destination; 415 wrong content type; 429 process limit; 503 database/service failure. Errors contain no driver secrets. Responses use no-store.
- Guest requests do not write `applications` or `application_clicks`. Supplied bearer/Supabase session credentials are not silently downgraded to guest. Real authenticated processing and persistent idempotency belong to Phase 5.
- Process-wide limit: 120 attempts/minute, without retaining IP addresses. Replace/augment with shared deployment protection in Phase 6; this is not a distributed per-user limiter.

No new API key, package, migration, database grant or paid service is required. Existing `.env` settings are sufficient for local testing.

## Validation evidence

- Production build and TypeScript compilation passed.
- 14 web tests passed, including destination attacks, guest repeat requests, missing/ineligible jobs, injected database failures, bad origins/session credentials/bodies, rate-limit recovery and existing search tests.
- `python -m product.verify_apply`: 10 live HTTP checks passed; zero personal-record writes (before/after database counts).
- `python -m product.verify_api`: all 29 existing live checks passed, with 23 public listings.
- Browser: Apply entered its disabled checking state, then opened the matching Mirantis Software Engineer listing on Remote OK. No employer application was submitted. Back navigation restored the local page.
- Mobile apply control checked with no horizontal overflow (375 CSS-pixel content width). Desktop/mobile screenshots saved in the task's `outputs/product-phase4` folder.

The unavailable and outage branches were exercised in handler tests, not by changing real listing status or deliberately taking Supabase offline. Source availability remains the ingestion worker's seven-day check policy; a database eligibility recheck is not a fresh live employer check or a guarantee that hiring is still open.

## Handoff

Local application: `http://127.0.0.1:3000`. Restart from `C:\TalentPulse-AI\web` with `npm run build` then `npm run start`.

Next: Phase 5 Supabase authentication, saved jobs, and self-reported application tracking. Integrate session verification and atomic click recording before allowing account sessions through this endpoint. Keep `clicked` separate from `applied`, preserve existing self-reported statuses, and enforce idempotency and own-row access.
