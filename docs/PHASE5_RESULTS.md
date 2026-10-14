# Phase 5 — warehouse-backed analytics

Completed 17 September 2026. The existing six-table Snowflake architecture and approved dataset are retained. This phase executed read-only queries; it did not reload or modify warehouse tables.

## Implemented

`analytics/analyze_jobs.py` now reads Snowflake instead of the raw CSV. `analytics/warehouse_analytics.py` provides reusable extraction, reconciliation, summary and report functions for the future dashboard or assistant. There is no silent CSV fallback.

Reports include roles, categories, seniority, companies, source location labels, work modes, job types, posting-date distributions, source-tag prevalence, and role/tag combinations. Outputs are structured JSON and a readable Markdown report in `analytics/output`.

The engine validates the transformed input manifest and exact warehouse facts, dimension references and tag links before publishing. It also compares each SQL aggregate with an independent calculation over the approved local snapshot. Disagreements stop the run. Query IDs and the input hash are recorded in the JSON report.

Job totals use the job fact grain. Tags count distinct source jobs per exact tag; their percentages overlap and must not be added as a partition. Role/tag percentages use the number of jobs in that role as denominator. Unknown labels remain visible in denominators. Posting dates are a snapshot distribution, not a historical demand trend, and missing days are not invented as zero demand.

## Live results

- 32 approved jobs across 30 companies.
- Largest role groups: Software Engineer 12, IT / Technical Support 5, Data Analyst 3, technical Other 3.
- 23 populated location labels and 9 Unknown labels. Populated labels are not necessarily standardized geographic locations: some say Remote.
- 3 known work-mode labels, 29 Unknown; all 32 job types Unknown.
- 17 classified seniority values and 15 Other/unspecified values.
- 27 missing/zero salary ranges; five positive ranges. Salary averages, rankings and market estimates are suppressed because currency and pay period are absent.
- All SQL aggregates reconciled; all 48 offline tests passed.

The first reader validation caught an adapter mismatch between numeric zero and string zero salaries. It was corrected and covered by a regression test before the successful run. No warehouse correction was needed.

## Reproduce

Run from `C:\TalentPulse-AI`:

```powershell
.\venv\Scripts\python.exe analytics\analyze_jobs.py
.\venv\Scripts\python.exe -m unittest discover -s tests -q
```

Optional `--input` selects a transformed snapshot with its valid manifest; `--output` selects the report directory. Credentials use the existing local configuration and are never written to reports. Failed runs do not publish replacement reports; consumers should check exit status and the timestamp/input hash on any existing report.

## Next phase

Connect these validated outputs to the dashboard and, subsequently, grounded AI explanations. Display source coverage and missing-data limitations alongside the charts. Skill-demand claims require validation of the noisy source tags; salary comparisons require currency/pay-period enrichment. Neither was invented in this phase.

This remains one small RemoteOK snapshot reviewed by the assistant, not an independently human-annotated, representative job-market dataset.
