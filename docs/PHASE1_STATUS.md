# Phase 1 — access verification

Verified 15 September 2026 against the updated local configuration.

| Check | Result |
|---|---|
| AI configuration | API key and model are present; secret values were not printed. |
| Live AI request | Blocked: HTTP 429, `credit_balance_exhausted` / `insufficient_quota`. No classification returned. |
| Snowflake authentication | Passed using the new account. |
| Existing loader connection | Passed with the configured database, schema and warehouse. |
| Target | `TALENTPULSE.JOB_ANALYTICS`, `COMPUTE_WH`. |
| Warehouse execution | Passed a query generating and summing 1,000 values; result 499,500. |
| Required tables and columns | All six tables and required columns exist, including `SOURCE_JOB_ID`. |
| Current row counts | All six tables are empty, verified by COUNT queries. |
| Data changes | None. No classified dataset or warehouse replacement was produced. |
| Warehouse after check | Returned to its original suspended state to avoid idle runtime. Auto-resume remains enabled. |

Phase 1 is not fully complete because AI generation is still blocked. Add credits to the API organization/project associated with the configured key, then repeat the single-request smoke check. If it succeeds, proceed to Phase 2's 17-case live classification evaluation.

Evidence: `phase1_ai.json` and `phase1_snowflake.json` in the Codex task output directory. The Snowflake report includes inspected table definitions and the compute query ID. This check confirms access and expected columns; it does not validate a full data load or model accuracy.
