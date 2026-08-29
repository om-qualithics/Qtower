#!/bin/bash
# One-time setup: generates the Fernet key used by apps/api/core/crypto.py
# to encrypt secrets at rest (currently: a GitHub App's private key,
# modules/codescan). Requires the `cryptography` package - already a
# dependency of this repo's venv (pulled in by pyjwt[crypto]).
set -e

KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
  || python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

echo "ENCRYPTION_KEY value for infra/.env:"
echo "$KEY"
