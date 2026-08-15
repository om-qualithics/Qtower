"""Idempotent one-time setup: creates the single org row this container
serves (handoff §2.1 - exactly one org per v1 deployment). Not run
automatically on boot; run manually once per fresh deployment:

    python -m apps.api.scripts.seed_org "Acme Inc"
"""
import sys

from sqlalchemy import select

from apps.api.core.db import SessionLocal
from apps.api.modules.identity.models import Org


def seed_org(name: str) -> Org:
    db = SessionLocal()
    try:
        existing = db.scalars(select(Org)).first()
        if existing is not None:
            print(f"Org already exists: {existing.name} ({existing.id})")
            return existing

        org = Org(name=name)
        db.add(org)
        db.commit()
        db.refresh(org)
        print(f"Created org: {org.name} ({org.id})")
        return org
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m apps.api.scripts.seed_org \"Org Name\"")
        sys.exit(1)
    seed_org(sys.argv[1])
