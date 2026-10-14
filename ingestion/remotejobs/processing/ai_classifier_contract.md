# AI classifier contract

Implemented file: `ai_classifier.py`. See `docs/CLASSIFICATION_RUNBOOK.md` for execution and review.

Input: `ingestion/output/clean_jobs.csv`

Output: `ingestion/output/ai_classified_jobs.csv`

Required fields:
- `is_tech_job`: boolean
- `role`: controlled vocabulary
- `category`: controlled vocabulary
- `experience_level`: controlled vocabulary
- `ai_confidence`: 0.0 to 1.0

The classifier should use job title and tags as inputs, use structured output, classify semantic meaning rather than substring matches, and preserve one output row per input row.

Implementation adds a short reason, model/version/source-hash provenance, original prediction,
explicit failure status and review fields. Failed classifications retain their source row with
blank semantic values. All successful rows, including non-tech exclusions, require review in
`reviewed_jobs.csv` before transformation. Confidence is a model self-assessment.

`classification_contract.py` contains the controlled vocabulary and consistency checks.
`evaluate_classifier.py` runs the live model against 17 curated regression cases; the offline
unit tests do not substitute for this semantic evaluation.
