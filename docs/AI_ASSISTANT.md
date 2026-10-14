# TalentPulse grounded analytics assistant

Implemented and verified on 21 September 2026 within the existing local dashboard.

## Use

Start `venv\Scripts\python.exe dashboard\server.py` from `C:\TalentPulse-AI`, then open http://127.0.0.1:8765/#assistant. Select **Ask TalentPulse**, enter a question, and expand **Supporting evidence** to inspect the cited report values. The existing local `GEMINI_API_KEY`, `GEMINI_MODEL` and request-spacing settings are reused. No OpenAI fallback is used.

Questions are independent. Answers remain in the browser page until reload; they are not stored as conversation history. Each answer identifies the exact report hash, report validation time, posting-date range, model and scope. Refreshing analytics is a separate dashboard operation and does not ingest new postings.

## Architecture

Dashboard → same-origin `/api/ask` → current validated report gate → Gemini structured question interpretation → local answer/evidence renderer → dashboard.

Gemini receives the question and catalog labels, not credentials or arbitrary warehouse access. It returns a restricted query plan: an allowed topic, an exact catalog entity or null, and a result limit. Pydantic rejects extra fields, unsupported topics and invalid limits. The existing bounded Gemini transport is reused through its new generic `generate` method; classification behavior remains covered by the existing tests.

Application code renders every displayed claim and numerical citation from the report. Model-authored prose, SQL and tool commands are never executed or presented as an answer. An invalid entity or failed provider request produces an error instead of an unverified answer. This bounds numerical fabrication; Gemini can still misunderstand which supported topic the user intended, so the UI shows the answer's topic and evidence for inspection.

Supported questions cover totals, role/category/company/location/seniority/work-mode/job-type distributions, source tags, tags within one role and data coverage. Location labels are not standardized geography, and source tags are not validated skill requirements. Unsupported combinations, job-level records, arbitrary SQL, career recommendations and unrelated requests receive an explicit limitation response.

Salary requests report insufficient data because currency/pay period are missing. Historical growth and forecasts are unavailable because one snapshot is not a longitudinal dataset. The report validation time is not a new ingestion date. No new warehouse data was loaded during this implementation.

## Controls and errors

- Local server and existing Host/Origin checks remain in place.
- Questions must be JSON strings of 1–1000 characters; request bodies are bounded.
- A lock permits one question at a time; concurrent requests get a retryable response.
- The current report must match the transformation manifest and both reconciliation flags.
- Provider failures are sanitized; no credential-bearing errors are returned to the browser.
- Labels, questions and responses are rendered as text, not executable HTML.
- A question is sent to Google's configured Gemini API. The UI states this explicitly.

This remains a local application, not an authenticated public service or a guarantee against all semantic misinterpretations.

## Verification

58 offline tests passed. New tests cover changed report values, citation resolution, unknown entities, salary/trend limitations, strict model output, input bounds and role-tag denominators. Existing provider/classification/dashboard tests continued to pass.

Eight live Gemini checks passed: top roles, exact Software Engineer count, company rankings, Data Engineer tags, salary comparison limitation, growth limitation, a secret/SQL prompt-injection attempt, and an unsupported company-plus-role filter. These are smoke/regression checks, not a representative accuracy estimate. The task output `assistant_live_validation.json` contains questions, plans, expected topics and rendered evidence.

Browser verification confirmed submission through the real endpoint, the answer **12 Software Engineer jobs (37.5%)**, expandable citation to `distributions.roles.0`, salary limitation with evidence, mobile width without horizontal overflow, and a visible error when the question request was deliberately blocked. Invalid body and cross-origin API checks passed. No warehouse writes occurred.
