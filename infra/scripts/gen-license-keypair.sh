#!/bin/bash
# One-time setup: generates the RSA keypair used to sign/verify license
# files. Private key never leaves this machine (or wherever the internal
# license-generation CLI is later run from) and must never ship in a
# Docker image - see aboutproject.md Milestone 3 for the open question on
# long-term production key storage.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/secrets"
mkdir -p "$DIR"

openssl genrsa -out "$DIR/license_signing_key.pem" 2048 >/dev/null 2>&1
openssl rsa -in "$DIR/license_signing_key.pem" -pubout -out "$DIR/license_public_key.pem" >/dev/null 2>&1

echo "Keypair written to $DIR"
echo
echo "LICENSE_PUBLIC_KEY value for infra/.env (base64, matches the"
echo "mock-saml cert convention):"
base64 -w0 "$DIR/license_public_key.pem"
echo
