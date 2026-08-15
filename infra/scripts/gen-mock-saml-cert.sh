#!/bin/bash
# One-time local dev helper: generates a self-signed cert/key pair for the
# mock-saml container to sign SAML assertions with, and prints the env
# values to paste into infra/.env. Not needed once a real IdP is in use.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/dev-certs"
mkdir -p "$DIR"

MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -keyout "$DIR/mock-saml-key.pem" \
  -out "$DIR/mock-saml-cert.pem" -days 3650 -nodes \
  -subj "/CN=mock-saml.local" >/dev/null 2>&1

echo "MOCK_SAML_PUBLIC_KEY=$(base64 -w0 "$DIR/mock-saml-cert.pem")"
echo "MOCK_SAML_PRIVATE_KEY=$(base64 -w0 "$DIR/mock-saml-key.pem")"
