"""One-time setup script (same convention as gen-license-keypair.sh /
gen-mock-saml-cert.sh): prompts for the break-glass super-admin's email +
password, hashes the password with bcrypt, and writes SUPER_ADMIN_EMAIL /
SUPER_ADMIN_PASSWORD_HASH_B64 into infra/.env - never stores the plaintext
password anywhere. Re-running replaces any existing values (e.g. to
rotate the password). The backend must be restarted for this to take
effect (env is only read at process startup, same as every other setting).

The hash is stored base64-encoded, not as the raw bcrypt string - a
bcrypt hash always contains literal `$` characters, and Docker Compose's
env_file loading interpolates `$word` as a `${word}` variable reference,
silently corrupting the value when it's passed into a container this way
(see core/settings.py's super_admin_password_hash_b64 docstring).

    python -m apps.api.scripts.set_super_admin_password
"""
import base64
import getpass
import sys
from pathlib import Path

import bcrypt

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = REPO_ROOT / "infra" / ".env"


def _upsert_env_var(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{prefix}{value}"
            return lines
    lines.append(f"{prefix}{value}")
    return lines


def main() -> None:
    if not ENV_PATH.exists():
        print(f"{ENV_PATH} not found - copy infra/.env.example to infra/.env first.", file=sys.stderr)
        sys.exit(1)

    email = input("Super admin email: ").strip()
    if not email:
        print("Email is required.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not password:
        print("Password is required.", file=sys.stderr)
        sys.exit(1)
    if password != confirm:
        print("Passwords did not match.", file=sys.stderr)
        sys.exit(1)

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    password_hash_b64 = base64.b64encode(password_hash.encode("utf-8")).decode("utf-8")

    lines = ENV_PATH.read_text().splitlines()
    lines = _upsert_env_var(lines, "SUPER_ADMIN_EMAIL", email)
    lines = _upsert_env_var(lines, "SUPER_ADMIN_PASSWORD_HASH_B64", password_hash_b64)
    ENV_PATH.write_text("\n".join(lines) + "\n")

    print(f"\nWrote SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD_HASH_B64 to {ENV_PATH}.")
    print("Restart the backend for this to take effect.")


if __name__ == "__main__":
    main()
