#!/bin/bash
# Jackson (SAML/OIDC + SCIM broker) manages its own schema/migrations and
# is not tenant data, so it gets its own database rather than living in
# the app's RLS-protected schema. Runs once on first container init, same
# convention as 01-app-role.sh.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE DATABASE "${JACKSON_DB_NAME}";
  GRANT ALL PRIVILEGES ON DATABASE "${JACKSON_DB_NAME}" TO "${POSTGRES_USER}";
EOSQL
