# TalentPulse AI: classification and warehouse reload

Updated 15 September 2026. This extends the existing project at `C:\TalentPulse-AI` and its six-table dimensional model. The original handoff is historical context; this document describes the implemented continuation.

## Current status

- Gemini is configured and passed Phase 2: all 17 live regression cases matched, with no request errors. See `docs/PHASE2_RESULTS.md`.
- The default is `AI_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.1-flash-lite`, with seven-second request spacing. The OpenAI provider remains optional and is never an automatic fallback.
- All 42 offline tests pass. Classification, review validation, transformation and transactional reload remain integrated in the existing architecture.
- The new Snowflake account passed connection, compute and required-column checks in Phase 1; its six tables were empty. Phase 2 made no warehouse changes.
- Phase 3 processed 99 fresh postings with zero API failures: 32 approved technical jobs, 62 approved exclusions and 5 explicitly quarantined rows. The assistant reviewed source evidence for every row and corrected semantic labels on 32 rows. See `docs/PHASE3_RESULTS.md`; this is not independent human validation.
- Phase 4 is complete: the rebuilt 32-job snapshot passed rehearsal/rollback, committed successfully, and reconciled from a new connection. See `docs/PHASE4_RESULTS.md`. Warehouse-backed analytics are next.

## Pipeline

RemoteOK → existing fetcher → raw CSV → existing cleaner → AI classifier → review of every row → transformed tech-only snapshot → Snowflake.

The fetcher now persists all fetched postings and their API IDs. The obsolete keyword filter remains available for historical reference but is not called by `run()`. Cleaning preserves job IDs as strings. Old CSVs without IDs receive a deterministic URL-based ID during classification; missing IDs and URLs, or duplicate identities, fail before API requests.

Missing locations remain `Unknown` with `location_missing=true` rather than causing valid postings to be dropped. `ftfy.fix_encoding` repairs recoverable mojibake while preserving Unicode. Original raw data and full API descriptions are archived for review; irrecoverable source text is not guessed.

Classification uses title and tags only. The prompt treats both as untrusted data and prioritizes actual occupational meaning over noisy technology tags. Structured output controls role, category and seniority. Local validation also checks role/category consistency, finite confidence and non-tech labels. Unstated seniority is `Other`, not automatically `Mid`. Confidence is self-reported, not calibrated accuracy.

The fixed output vocabulary is a warehouse contract, not a keyword matching system. It retains the earlier roles and adds QA/testing, IT support, UX/UI and hardware/embedded coverage. `Other` remains valid for technical occupations outside that vocabulary.

## Configure and validate the AI provider

The local `.env` now contains GEMINI_API_KEY and selects Gemini. Do not commit the file. Model and request pacing can be changed with GEMINI_MODEL and GEMINI_MIN_INTERVAL. Use --provider openai explicitly if you later choose OpenAI and configure its key/model; there is no automatic paid fallback.

Run from the project root:

```powershell
Set-Location C:\TalentPulse-AI
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe ingestion\remotejobs\processing\evaluate_classifier.py
.\venv\Scripts\python.exe ingestion\remotejobs\processing\ai_classifier.py
```

The evaluation runs the real model against 17 curated examples, including clear tech roles, noisy non-tech tags, placeholders, the `ai` substring trap, and an injected instruction in a title. It writes `ingestion/output/classifier_evaluation.json` and exits nonzero on any exact-label mismatch or API error. It is a smoke evaluation, not a representative accuracy estimate. Inspect disagreements before changing prompts or vocabulary. Do not tune rules to reach a desired output count.

The classifier writes `ingestion/output/ai_classified_jobs.csv`, retaining one row per cleaned input, including non-tech jobs and failed requests. Successful results are cached by model, prompt/schema version, title and tags. Reruns reuse validated cache entries; failures are retried. API requests use bounded retries and timeouts; Gemini requests also use configurable pacing. Failures have blank semantic fields and an explicit `classification_status=error`; they are never silently labeled non-tech. A run containing failures exits with code 2 after saving the reviewable output.

If a fresh snapshot is needed to recover postings discarded by the earlier filter, first archive the existing CSVs, then run the existing fetcher and cleaner. This produces a new source snapshot; it cannot recover the historical omitted records:

```powershell
.\venv\Scripts\python.exe ingestion\remotejobs\fetch_jobs.py
.\venv\Scripts\python.exe ingestion\remotejobs\processing\clean_jobs.py
```

## Review and transform

Copy `ai_classified_jobs.csv` to `reviewed_jobs.csv`. Inspect every row, including proposed exclusions. Keep every row and source field intact. For each successful classification:

1. Check the proposed tech flag, role, category, experience and reason against the title and actual responsibilities in the saved source description. Treat tags as noisy supporting evidence and distinguish employer activities from the job's own duties.
2. Correct semantic fields when supported; retain `original_prediction` as the initial model output and explain corrections in `review_note`.
3. Set `review_status` to `approved` and set `reviewer` to the actual reviewer. Do not approve failed requests or unresolved classifications. Rerun failures. For unresolved source evidence, retain the original prediction, set `review_status=quarantined`, and record the actual reviewer and evidence limitation in `review_note`. Quarantine does not mean non-tech; those rows remain outside the warehouse subset.

Phase 3 adds `review_action`, `review_changed_fields`, `reviewed_at`, `review_evidence` and `review_source_sha256` to preserve the decision record. `original_prediction` and the original model confidence remain unchanged; `ai_confidence` is not a confidence score for corrected labels. The reviewer is explicitly recorded as the Codex assistant, not a human reviewer.

`needs_review` prioritizes low-confidence and Other results, but does not waive review for any row. CSV review fields are an operational record, not a tamper-proof approval system. Preserve UTF-8 and string IDs when editing.

Then run:

```powershell
.\venv\Scripts\python.exe ingestion\remotejobs\processing\transform_jobs.py
```

Transformation checks exact source ID coverage, source content hashes and review status before selecting `is_tech_job=true`. It retains AI semantic fields, normalizes dates and salaries, deduplicates skill tags, and uses `Unknown` when work mode or job type has no explicit evidence. It does not overwrite the full classified/reviewed datasets. Skill tags remain source tags; the classification layer does not certify each tag as a genuine job requirement.

Outputs are `transformed_jobs.csv` and `transformed_jobs.csv.manifest.json`. The manifest links hashes of the source, reviewed and transformed files plus expected table counts. The loader re-runs transformation from those inputs during preflight. Edited or moved inputs require rebuilding the manifest. An all-non-tech result can be saved and inspected, but cannot empty the warehouse through the reload command.

## Reload the existing warehouse

Access to the newly configured Snowflake account was verified on 15 September. COMPUTE_WH can auto-resume and execute queries. No billing change was made by this task.

```powershell
# Offline preflight and replacement plan; no Snowflake connection:
.\venv\Scripts\python.exe warehouse\snowflake_loader.py

# Exercise the full replacement, reconcile, then ROLLBACK:
.\venv\Scripts\python.exe warehouse\snowflake_loader.py --rehearse

# Exercise the same replacement, reconcile, then COMMIT:
.\venv\Scripts\python.exe warehouse\snowflake_loader.py --apply
```

The strategy is a full snapshot replacement of `TALENTPULSE.JOB_ANALYTICS`'s six existing tables. It intentionally removes previously loaded jobs excluded from this corrected snapshot, stale skill links and unused dimensions. It regenerates surrogate IDs while preserving source IDs. This is appropriate for the requested rebuild; it is not an incremental historical archive. Run with no concurrent writers. Other systems should not depend on old surrogate IDs surviving this rebuild.

The loader checks target identity and table presence, opens one transaction, deletes child rows before parent rows, runs the existing dimension/fact MERGE helpers, and validates before committing. Fact MERGE now also updates existing values when matched. No DDL or TRUNCATE occurs in the transaction. Any load/validation failure triggers rollback. Before committing, it checks:

- Exact counts for all six tables.
- Every source job ID and all loaded fact attributes against the reviewed snapshot.
- Dimension references through reconstructed facts.
- Exact job/skill relationships, detecting missing, duplicate, stale or orphaned links.
- Unique non-null surrogate keys.

The report records input hash, counts and whether the run committed. `schema.sql` uses `CREATE TABLE IF NOT EXISTS` as a separate bootstrap aid; it does not drop tables and does not migrate existing definitions. Run it only if schema bootstrap is actually required. A missing `SOURCE_JOB_ID` on an older table requires an explicit migration before reload. The inherited salary columns use whole-number Snowflake `NUMBER`; if fractional values are rounded by the existing schema, exact reconciliation fails and rolls back rather than silently accepting that loss.

After a successful commit, validate dashboard/analytics queries against the report. If the dataset later needs correction, repair the review inputs and repeat the full validated load. Rollback protects failures before commit; it is not a post-commit backup. Preserve prior source/reviewed datasets and follow the account's retention policy for recovery.

## Validation limits and references

The offline suite tests both provider boundaries and transaction control with mocked calls. Gemini passed all 17 live curated evaluation cases; this is not a representative estimate of production accuracy. Phase 4 exercised the full reload SQL, verified rehearsal rollback, and verified the committed snapshot from a new connection. Source quality limitations remain documented in the phase reports.

The structured response integration follows [OpenAI's structured outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs). The chosen configurable snapshot supports structured output according to the [GPT-4.1 mini model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini). The reload avoids DDL inside the transaction because it implicitly commits, as described in [Snowflake's transaction documentation](https://docs.snowflake.com/en/sql-reference/transactions).
