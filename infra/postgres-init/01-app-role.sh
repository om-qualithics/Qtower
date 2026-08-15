#!/bin/bash
# Runs once, automatically, on first init of an empty Postgres data volume
# (official postgres image convention: /docker-entrypoint-initdb.d).
#
# Creates a non-superuser role for the application to connect as at
# runtime. The POSTGRES_USER role is a superuser (initdb default) and
# superusers unconditionally bypass Row-Level Security, even with FORCE
# ROW LEVEL SECURITY on the table - so multi-tenant isolation (handoff
# §2.1) can only be enforced if the app connects as a different, restricted
# role. POSTGRES_USER stays reserved for Alembic migrations (DDL).
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE ROLE "${APP_DB_USER}" LOGIN PASSWORD '${APP_DB_PASSWORD}';
  GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO "${APP_DB_USER}";
  GRANT USAGE ON SCHEMA public TO "${APP_DB_USER}";
  ALTER DEFAULT PRIVILEGES FOR ROLE "${POSTGRES_USER}" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "${APP_DB_USER}";
  ALTER DEFAULT PRIVILEGES FOR ROLE "${POSTGRES_USER}" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO "${APP_DB_USER}";
EOSQL
