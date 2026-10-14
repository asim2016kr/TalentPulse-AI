-- Separate role memberships from credentials. Login passwords are provisioned
-- server-side by product.provision_access, never stored in migration files.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='talentpulse_read') THEN
    CREATE ROLE talentpulse_read NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='talentpulse_preview') THEN
    CREATE ROLE talentpulse_preview NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='talentpulse_ingest') THEN
    CREATE ROLE talentpulse_ingest NOLOGIN;
  END IF;
END $$;
GRANT talentpulse_read, talentpulse_preview, talentpulse_ingest TO CURRENT_USER;
GRANT USAGE ON SCHEMA app TO talentpulse_read, talentpulse_preview, talentpulse_ingest;

GRANT SELECT (id,company_id,title,description_text,location_text,work_mode,job_type,
 role,category,experience_level,source_tags,published_at,source,source_url,
 application_url,application_url_kind,status,is_development,freshness_checked_at,
 fresh_until,expires_at,updated_at,search_document) ON app.jobs TO talentpulse_read, talentpulse_preview;
GRANT SELECT (id,name,domain,website_url) ON app.companies TO talentpulse_read, talentpulse_preview;
CREATE POLICY jobs_reader ON app.jobs FOR SELECT TO talentpulse_read
 USING (NOT is_development AND status IN ('active','expired'));
CREATE POLICY companies_reader ON app.companies FOR SELECT TO talentpulse_read USING (true);
CREATE POLICY jobs_preview ON app.jobs FOR SELECT TO talentpulse_preview USING (true);
CREATE POLICY companies_preview ON app.companies FOR SELECT TO talentpulse_preview USING (true);

GRANT SELECT, INSERT, UPDATE ON app.jobs, app.companies, app.ingestion_runs TO talentpulse_ingest;
GRANT EXECUTE ON FUNCTION app.touch_updated_at() TO talentpulse_ingest;
CREATE POLICY jobs_ingestion ON app.jobs TO talentpulse_ingest USING (true) WITH CHECK (true);
CREATE POLICY companies_ingestion ON app.companies TO talentpulse_ingest USING (true) WITH CHECK (true);
CREATE POLICY runs_ingestion ON app.ingestion_runs TO talentpulse_ingest USING (true) WITH CHECK (true);

-- Application data remains private until managed auth is implemented in Phase 5.
-- No user/saved/application permissions are granted to these job-read roles.
CREATE TABLE app.analytics_exports (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 ingestion_run_id uuid NOT NULL UNIQUE REFERENCES app.ingestion_runs(id),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','complete','failed')),
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts >= 0),
 completed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE app.analytics_exports ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app.analytics_exports FROM PUBLIC;
GRANT SELECT, INSERT ON app.analytics_exports TO talentpulse_ingest;
CREATE POLICY analytics_exports_ingestion ON app.analytics_exports TO talentpulse_ingest
 USING(true) WITH CHECK(true);
