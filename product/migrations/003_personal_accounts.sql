CREATE ROLE talentpulse_member NOLOGIN;
GRANT talentpulse_read TO talentpulse_member;
GRANT talentpulse_member TO CURRENT_USER;
GRANT USAGE ON SCHEMA app TO talentpulse_member;

CREATE FUNCTION app.current_member() RETURNS uuid LANGUAGE sql STABLE
SET search_path = pg_catalog AS $$ SELECT nullif(current_setting('app.user_id',true),'')::uuid $$;
REVOKE ALL ON FUNCTION app.current_member() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.current_member() TO talentpulse_member;

GRANT SELECT ON app.users TO talentpulse_member;
GRANT INSERT(id,email,display_name,email_verified_at,last_sign_in_at),
 UPDATE(email,email_verified_at,last_sign_in_at) ON app.users TO talentpulse_member;
CREATE POLICY users_self ON app.users TO talentpulse_member
 USING (id=app.current_member()) WITH CHECK (id=app.current_member());

CREATE FUNCTION app.member_enabled() RETURNS boolean LANGUAGE sql STABLE
SET search_path = pg_catalog AS $$
 SELECT EXISTS (SELECT FROM app.users WHERE id=app.current_member() AND disabled_at IS NULL AND email_verified_at IS NOT NULL)
$$;
REVOKE ALL ON FUNCTION app.member_enabled() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.member_enabled() TO talentpulse_member;
GRANT SELECT,INSERT,DELETE ON app.saved_jobs TO talentpulse_member;
GRANT SELECT,INSERT,UPDATE ON app.applications TO talentpulse_member;
GRANT SELECT,INSERT ON app.application_clicks TO talentpulse_member;
CREATE POLICY saves_self ON app.saved_jobs TO talentpulse_member
 USING (user_id=app.current_member() AND app.member_enabled())
 WITH CHECK (user_id=app.current_member() AND app.member_enabled());
CREATE POLICY applications_self ON app.applications TO talentpulse_member
 USING (user_id=app.current_member() AND app.member_enabled())
 WITH CHECK (user_id=app.current_member() AND app.member_enabled());
CREATE POLICY clicks_self ON app.application_clicks TO talentpulse_member
 USING (user_id=app.current_member() AND app.member_enabled())
 WITH CHECK (user_id=app.current_member() AND app.member_enabled());
CREATE INDEX saved_jobs_recent ON app.saved_jobs(user_id,created_at DESC,job_id);

-- Shared limits survive process restarts; no raw email or IP is persisted.
CREATE TABLE app.request_limits (key text PRIMARY KEY, hits integer NOT NULL, expires_at timestamptz NOT NULL);
CREATE INDEX request_limits_expiry ON app.request_limits(expires_at);
ALTER TABLE app.request_limits ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app.request_limits FROM PUBLIC;
CREATE FUNCTION app.consume_limit(p_key text,p_scope text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE max_hits integer; duration interval; n integer;
BEGIN
 IF length(p_key)>80 OR length(p_key)<1 THEN RAISE EXCEPTION 'Invalid limit key'; END IF;
 CASE p_scope
 WHEN 'auth_global' THEN max_hits:=60; duration:=interval '1 minute';
 WHEN 'auth_account' THEN max_hits:=10; duration:=interval '15 minutes';
 WHEN 'action' THEN max_hits:=120; duration:=interval '1 minute';
 ELSE RAISE EXCEPTION 'Invalid limit scope'; END CASE;
 DELETE FROM app.request_limits WHERE expires_at<now();
 INSERT INTO app.request_limits(key,hits,expires_at) VALUES(p_scope||':'||p_key,1,now()+duration)
 ON CONFLICT(key) DO UPDATE SET hits=app.request_limits.hits+1 RETURNING hits INTO n;
 RETURN n<=max_hits;
END $$;
REVOKE ALL ON FUNCTION app.consume_limit(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.consume_limit(text,text) TO talentpulse_member;
