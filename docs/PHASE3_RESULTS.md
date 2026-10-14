# TalentPulse AI — Phase 3 results

Snapshot collected and reviewed on 15 September 2026. Existing architecture retained; no Snowflake connection or data modification occurred in this phase.

## Outcome

| Measure | Result |
|---|---:|
| Raw / cleaned / classified postings | 99 / 99 / 99 |
| Gemini request failures | 0 |
| Approved technical postings | 32 |
| Approved exclusions | 62 |
| Unresolved postings quarantined | 5 |
| Rows with corrected semantic labels | 32 |
| Tech/non-tech flag corrections | 10: five inclusions, five exclusions |
| Offline tests passed | 42 |

Every posting has an explicit source-review decision. Review was performed by the Codex assistant using titles and saved descriptions, not an independent human annotator. These counts measure review decisions, not verified population accuracy. Original Gemini predictions remain intact alongside corrections.

## Data preservation and cleaning

Previous datasets were archived with hashes under `data/archive/20260915T062929Z`. The full new API payload, including descriptions used as evidence, is at `data/snapshots/20260915T062929Z/source_jobs.json`.

The old cleaner would have discarded 30 postings without locations. These now remain as `Unknown`, explicitly flagged with `location_missing`. Eight recoverable encoding errors were repaired across eight records. Raw source text remains preserved; incomplete corruption in the DoiT sales title is not guessed.

The current dataset has 87 zero/zero salary pairs. These must not be interpreted as actual zero salaries in analytics. Nine approved technical postings have unknown locations. Source tags remain noisy and are not validated skill requirements. This is one 99-posting source snapshot, not evidence of historical or whole-market hiring trends.

## Review findings

Title/tag-only classification missed real technical support work in Warehance and Resource Guru customer-support postings, and field IT deployment work in SLB's drilling-operations posting. It also missed a data analyst assistant and a hybrid HRIS automation role whose technical duties were explicit in their descriptions.

Conversely, manual AI content rating, UX course creation, video/motion design and building-services maintenance were incorrectly included as technical occupations. These were excluded using actual duties. Role corrections also distinguish Oracle ERP implementation from DevOps, and game-level scripting from UX/UI.

The current vocabulary retains technical `Other` for ERP implementation, game-level scripting and HRIS automation. Seniority remains `Other` where unclear; employer-specific II/III grades are not assumed to map to Mid/Senior. Staff uses the existing broad Senior bucket without implying Principal equivalence. These taxonomy choices are documented in the review notes.

The original model confidence is preserved even when the label changes. It is not a score for the corrected label, and high model confidence does not waive review. Automated production approval remains inappropriate for this title/tag-only classifier; description-aware classification and a separately annotated evaluation set are future improvements.

## Unresolved records

| Job ID | Posting | Reason held out |
|---|---|---|
| 1137375 | External Data Specialist — eClinical Solutions | Description ends before duties |
| 1137162 | Principal Engineer — AI Whistleblower Initiative | Generic title plus tags; excerpt contains only mission text |
| 1136937 | Solutions Delivery Manager — Benchling | Scientific enablement versus technical implementation boundary needs domain review |
| 1136778 | Operations Engineer II — AWeber | Generic website/careers copy instead of responsibilities |
| 1136370 | Functional Assessor — PFAS | No usable readable description after HTML decoding |

Quarantined rows retain their original, unapproved model predictions. They are neither approved technical jobs nor confirmed non-tech exclusions. The transformer now permits an explicitly documented quarantine while excluding those rows from warehouse input. It still rejects missing reviewers, missing quarantine notes, failed API classifications and altered source content.

## Saved outputs and validation

`ingestion/output/reviewed_jobs.csv` is the complete 99-row decision ledger. The companion files `tech_jobs_reviewed.csv`, `excluded_jobs_reviewed.csv`, and `quarantined_jobs.csv` expose its three subsets. `phase3_review_changes.csv` records corrections and holds. `phase3_validation.json` records counts, paths and hashes. `docs/phase3_review_decisions.json` contains this snapshot's explicit review decisions.

Validated exact ID coverage, unique identities, source hashes, classification schema, preserved original predictions, and 32 + 62 + 5 = 99 reconciliation. The actual transformation function passed against saved reviewed inputs in memory. All 42 offline tests passed, including missing-location/Unicode handling and quarantine guards. Production transformed files were not rebuilt in this phase.

## Next phase

Phase 4 should rebuild `transformed_jobs.csv` and its manifest from the complete reviewed ledger, run offline loader preflight, rehearse the transactional Snowflake replacement with rollback, then apply and reconcile. Old transformed outputs are stale and must not be loaded directly.

Current expected counts from the in-memory transformation: 32 job facts, 30 companies, 21 locations, 16 role/seniority combinations, 84 distinct source tags, and 439 job/tag links. These are expected counts only; nothing has been loaded. Source tags should be described as tags until skill validation is completed.
