# TalentPulse dashboard

The dashboard lives in the existing Python repository and serves the Phase 5 validated analytics. It is local to this computer, not a hosted public application. No new framework dependencies were required.

## Start

From `C:\TalentPulse-AI`:

```powershell
.\venv\Scripts\python.exe dashboard\server.py
```

Open http://127.0.0.1:8765. An optional `--port` changes the port. The process must remain running while using the dashboard.

## Data flow

On page load, `/api/report` checks the saved analytics report against the current transformed-input manifest and requires both reconciliation flags. It serves the last validated snapshot, not an unverified live query. The timestamp shows when analytics was validated, not when source postings were collected.

**Refresh from Snowflake** calls a same-origin POST endpoint, runs the existing read-only analytics collector and exact reconciliation, then atomically updates the report. The browser polls refresh status. Only one refresh can run at a time. Failed refreshes retain the previous report and expose a sanitized error message. Refresh does not ingest new jobs or reload the warehouse.

Credentials stay in the local Python process. Only explicit static assets and report/status/download endpoints are served; the repository and `.env` are not exposed. The server binds to loopback and checks Host and Origin. This is a local tool, not a production authentication system; do not expose it through a public tunnel without adding authentication and deployment hardening.

## Views

- Overview: snapshot totals, roles, seniority, searchable companies, and posting-date distribution.
- Source tags: exact source labels, role selection and text search. Clicking an overview role opens its tags. Role-specific percentages use that role's denominator; top cards remain snapshot-wide.
- Data coverage: missing labels, unavailable salary comparisons, review inclusion/exclusion counts, limitations and provenance.
- Export JSON: downloads the current validated report from a dedicated attachment endpoint.

Source values are rendered as text rather than HTML. Missing-data limitations, source-tag uncertainty and snapshot scope remain visible.

## Verification — 17 September 2026

51 offline tests passed, including stale/unvalidated report rejection and safe refresh-failure behavior. Browser checks exercised report rendering, role drill-down, tag-search empty state, navigation, mobile layout with no horizontal overflow, and a real Snowflake refresh. The refresh returned successfully and the displayed validation time updated. Simulated report-network failure displayed an error and normal loading recovered after restoring access.

The export attachment endpoint returned HTTP 200 and JSON matched the validated report. The browser automation download helper reported cancellation, so automated filesystem confirmation of the native browser download remains unverified.

No warehouse tables were changed. The local report was refreshed through the existing Phase 5 collector.

## Grounded AI assistant

Ask TalentPulse is now available at /#assistant. See `docs/AI_ASSISTANT.md` for the Gemini question interpreter, deterministic answers, citations and validation limits.
