# TalentPulse — job discovery and external applications

TalentPulse's product is a job platform: browse/search jobs, view descriptions,
create an account, save jobs and apply through an external source/employer site.
The existing Python ingestion/classification pipeline is retained. PostgreSQL serves
the application; Snowflake is reserved for downstream analytics.

Current product phase: **Phase 6 hardening and no-email QA implemented; email round-trip
verification and production release gates remain open**. The local job board runs
at `http://127.0.0.1:3000`. It includes search, external apply, Supabase account
flows, saved jobs and self-reported application tracking. The October 12 refresh
published 23 checked jobs; 38 source records remain pending review. Freshness is
enforced at runtime, so visible counts can change.

See [Phase 6 results](docs/PRODUCT_PHASE6_RESULTS.md),
[release runbook](docs/RELEASE_RUNBOOK.md),
[Phase 5 account features](docs/PRODUCT_PHASE5_RESULTS.md),
[Phase 4 external apply](docs/PRODUCT_PHASE4_RESULTS.md),
[Phase 3 interface](docs/PRODUCT_PHASE3_RESULTS.md), and
[Phase 2 backend](docs/PRODUCT_PHASE2_RESULTS.md).

Phase 1 specification and historical foundation validation:
See [Product architecture, API and setup](docs/PRODUCT_PHASE1.md) and
[Validation status](docs/PRODUCT_PHASE1_VALIDATION.md). The schema and 32-job
development seed were subsequently executed and validated on PostgreSQL in Phase 2.
Phase 6 is full-flow hardening and QA; Phase 7 is deployment and launch readiness.

The material below describes the historical analytics prototype, not the current
product roadmap. Prior analytics validation remains in `docs/PHASE5_RESULTS.md`.

## Historical project overview

TalentPulse-AI collect job data from multiple sources, processes it through a data pipeline, store it in Snowflake, and provides analytics and AI-powered insights through an interactive dashboards.

##Problem Statement
Job seekers and analysts struggle to understand hiring trends, salary patterns, and skill demand across different platforms. TalentPulse aims to centralize and analyze this Information.

##Architecture
Job Sources
|
Ingestion Layer
|
Raw Storage
|
Apache Airflow
|
Snowflake Data Warehouse
|
Analytics Engine
|
AI Assistant
|
Dashboard

##Tech Stack
-Python
-Snowflake
-Apache Airflow
-Pandas
-Gemini API
-Git & Github

##Roadmap

Phase 1
-Project setup
-Snowflake configuration
-Architecture Design


Phase 2
-Data Ingestion Pipeline
-Job Data Collection

Phase 3
-Data Warehouse Implementation

Phase 4
-Analytics engine

Phase 5
-AI assistant integration

Phase 6
-Dashboard development


##Future Scope
-Real-time job monitoring
-Resume matching
-Salary prediction
-Skill gap analysis
-Interview preparation assistant
