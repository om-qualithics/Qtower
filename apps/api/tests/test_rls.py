from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.identity.models import Org, User


def _make_org(name: str) -> Org:
    db = SessionLocal()
    try:
        org = Org(name=name)
        db.add(org)
        db.commit()
        db.refresh(org)
        return org
    finally:
        db.close()


def _make_user(org: Org, email: str) -> User:
    # user is RLS-protected (WITH CHECK), so the insert itself must run
    # inside a session already scoped to the target org.
    with org_scoped_session(str(org.id)) as db:
        user = User(org_id=org.id, email=email)
        db.add(user)
        db.flush()
        db.refresh(user)
        db.expunge(user)
        return user


def _make_org_with_user(name: str, email: str) -> tuple[Org, User]:
    org = _make_org(name)
    user = _make_user(org, email)
    return org, user


def test_rls_isolates_users_by_org() -> None:
    org_a, user_a = _make_org_with_user("Org A", "a@example.com")
    org_b, user_b = _make_org_with_user("Org B", "b@example.com")

    with org_scoped_session(str(org_a.id)) as db:
        visible = {u.email for u in db.query(User).all()}
        assert visible == {"a@example.com"}

    with org_scoped_session(str(org_b.id)) as db:
        visible = {u.email for u in db.query(User).all()}
        assert visible == {"b@example.com"}

    # Cleanup: FORCE ROW LEVEL SECURITY applies to every role including the
    # table owner, so even test cleanup must go through an org-scoped
    # session to delete each org's own user row.
    with org_scoped_session(str(org_a.id)) as db:
        db.query(User).filter(User.id == user_a.id).delete(synchronize_session=False)
    with org_scoped_session(str(org_b.id)) as db:
        db.query(User).filter(User.id == user_b.id).delete(synchronize_session=False)

    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id.in_([org_a.id, org_b.id])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
