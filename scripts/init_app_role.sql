-- Non-superuser app role so FORCE RLS actually applies.
-- Run as the bootstrap superuser (traceiq in compose) after schema migrate:
--   PGPASSWORD=traceiq psql -h 127.0.0.1 -p 55432 -U traceiq -d traceiq -f scripts/init_app_role.sql

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'traceiq_app') THEN
    CREATE ROLE traceiq_app LOGIN PASSWORD 'traceiq' NOSUPERUSER NOBYPASSRLS;
  END IF;
END$$;

GRANT CONNECT ON DATABASE traceiq TO traceiq_app;
GRANT USAGE ON SCHEMA public TO traceiq_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO traceiq_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO traceiq_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO traceiq_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO traceiq_app;

-- Allow the app role to disable triggers only in tests via superuser; not granted here.
