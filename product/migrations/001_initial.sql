-- PostgreSQL 15+. Private schema; only backend connections may access it.
CREATE SCHEMA app;
REVOKE ALL ON SCHEMA app FROM PUBLIC;

CREATE TABLE app.users (
    id uuid PRIMARY KEY, -- verified Supabase Auth subject; never supplied by the browser
    email text NOT NULL CHECK (length(btrim(email)) > 3),
    display_name text CHECK (length(display_name) <= 100),
    email_verified_at timestamptz,
    last_sign_in_at timestamptz,
    disabled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
    -- Password hashes, sessions, recovery tokens live ONLY in Supabase Auth.
);
CREATE UNIQUE INDEX users_email_unique ON app.users (lower(email));

CREATE TABLE app.companies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_key text NOT NULL UNIQUE, -- source:name fallback, not a guessed domain
    name text NOT NULL CHECK (btrim(name) <> ''),
    domain text,
    website_url text CHECK (website_url ~ '^https://[^[:space:]]+$'),
    metadata jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.ingestion_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL,
    snapshot_sha256 text NOT NULL CHECK (snapshot_sha256 ~ '^[a-f0-9]{64}$'),
    reviewed_sha256 text NOT NULL CHECK (reviewed_sha256 ~ '^[a-f0-9]{64}$'),
    observed_at timestamptz NOT NULL,
    is_development boolean NOT NULL,
    imported_count integer NOT NULL CHECK (imported_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(source, snapshot_sha256, reviewed_sha256)
);

CREATE TABLE app.jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES app.companies(id) ON DELETE RESTRICT,
    ingestion_run_id uuid NOT NULL REFERENCES app.ingestion_runs(id),
    source text NOT NULL,
    source_job_id text NOT NULL,
    source_url text NOT NULL CHECK (source_url ~ '^https://[^[:space:]]+$'),
    application_url text NOT NULL CHECK (application_url ~ '^https://[^[:space:]]+$'),
    application_url_kind text NOT NULL CHECK (application_url_kind IN ('source_listing','employer')),
    title text NOT NULL CHECK (btrim(title) <> ''),
    description_text text NOT NULL CHECK (btrim(description_text) <> ''),
    location_text text,
    work_mode text NOT NULL DEFAULT 'Unknown' CHECK (work_mode IN ('Remote','Hybrid','On-site','Unknown')),
    job_type text NOT NULL DEFAULT 'Unknown',
    role text NOT NULL,
    category text NOT NULL,
    experience_level text NOT NULL,
    source_tags text[] NOT NULL DEFAULT '{}', -- unverified source metadata, NOT extracted skills
    classification jsonb NOT NULL CHECK (jsonb_typeof(classification) = 'object'),
    review_status text NOT NULL CHECK (review_status = 'approved'),
    source_content_sha256 text NOT NULL CHECK (source_content_sha256 ~ '^[a-f0-9]{64}$'),
    published_at timestamptz,
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    freshness_checked_at timestamptz,
    fresh_until timestamptz,
    expires_at timestamptz,
    status text NOT NULL DEFAULT 'unverified' CHECK (status IN ('unverified','active','expired')),
    status_reason text NOT NULL,
    is_development boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    search_document tsvector GENERATED ALWAYS AS
        (setweight(to_tsvector('english', title), 'A') ||
         setweight(to_tsvector('english', description_text), 'B')) STORED,
    UNIQUE(source, source_job_id),
    CHECK (last_seen_at >= first_seen_at),
    CHECK (status <> 'active' OR (freshness_checked_at IS NOT NULL AND fresh_until IS NOT NULL)),
    CHECK (fresh_until IS NULL OR fresh_until > freshness_checked_at),
    CHECK (NOT is_development OR status <> 'active')
);
CREATE INDEX jobs_search ON app.jobs USING gin(search_document);
CREATE INDEX jobs_tags ON app.jobs USING gin(source_tags);
CREATE INDEX jobs_browse ON app.jobs (status, published_at DESC, id DESC);
CREATE INDEX jobs_filters ON app.jobs (role, work_mode, experience_level);
CREATE INDEX jobs_company ON app.jobs(company_id);

CREATE TABLE app.saved_jobs (
    user_id uuid NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    job_id uuid NOT NULL REFERENCES app.jobs(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(user_id, job_id)
);

CREATE TABLE app.applications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    job_id uuid NOT NULL REFERENCES app.jobs(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'clicked' CHECK (status IN ('clicked','applied','interviewing','offer','rejected','withdrawn')),
    first_clicked_at timestamptz,
    last_clicked_at timestamptz,
    self_reported_applied_at timestamptz,
    status_updated_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(user_id, job_id),
    CHECK (last_clicked_at IS NULL OR first_clicked_at IS NOT NULL),
    CHECK (last_clicked_at IS NULL OR last_clicked_at >= first_clicked_at)
);
CREATE INDEX applications_user_status ON app.applications(user_id, status, updated_at DESC);
CREATE TABLE app.application_clicks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    job_id uuid NOT NULL REFERENCES app.jobs(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL, -- client-generated idempotency key, unique per user
    clicked_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(user_id, request_id)
);

CREATE FUNCTION app.touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$;
CREATE TRIGGER users_updated BEFORE UPDATE ON app.users FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER companies_updated BEFORE UPDATE ON app.companies FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER jobs_updated BEFORE UPDATE ON app.jobs FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER applications_updated BEFORE UPDATE ON app.applications FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();

-- Defense in depth: no public/schema API access. RLS is closed until runtime
-- roles/policies are provisioned. Owner connection is for migration/ingestion only.
ALTER TABLE app.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.ingestion_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.saved_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.application_clicks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA app FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA app FROM PUBLIC;
