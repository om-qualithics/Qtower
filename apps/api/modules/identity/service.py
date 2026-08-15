import base64
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from sqlalchemy import select

from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.core.settings import settings
from apps.api.modules.identity.models import IdpGroupRoleMap, Org, OrgSsoConnection, User

JACKSON_PRODUCT = "misty"
SESSION_COOKIE_NAME = "misty_session"
SESSION_TTL = timedelta(hours=12)


def get_org() -> Org:
    """v1 runs exactly one org per container (handoff §2.1) - there is no
    org picker anywhere in the app, this resolves "the" org."""
    db = SessionLocal()
    try:
        org = db.scalars(select(Org)).first()
        if org is None:
            raise RuntimeError("No org configured - run apps/api/scripts/seed_org.py first")
        return org
    finally:
        db.close()


def create_sso_connection(org: Org, metadata_url: str) -> dict:
    """metadata_url is fetched by us, not handed to Jackson as a URL for it
    to fetch - Jackson only accepts localhost/HTTPS URLs for that, which
    breaks for our docker-network mock IdP in dev, and this way is also
    more robust in prod (one fetch path, not two)."""
    tenant = str(org.id)
    metadata_resp = httpx.get(metadata_url, timeout=10)
    metadata_resp.raise_for_status()
    encoded_metadata = base64.b64encode(metadata_resp.content).decode()

    resp = httpx.post(
        f"{settings.jackson_base_url}/api/v1/sso",
        headers={"Authorization": f"Api-Key {settings.jackson_api_keys}"},
        data={
            "encodedRawMetadata": encoded_metadata,
            "tenant": tenant,
            "product": JACKSON_PRODUCT,
            "defaultRedirectUrl": f"{settings.api_public_url}/identity/callback",
            "redirectUrl": f"{settings.api_public_url}/identity/callback",
            "name": f"{org.name} SSO",
        },
        timeout=10,
    )
    resp.raise_for_status()
    connection = resp.json()

    with org_scoped_session(tenant) as db:
        existing = db.scalars(
            select(OrgSsoConnection).where(OrgSsoConnection.org_id == org.id)
        ).first()
        if existing:
            db.delete(existing)
            db.flush()
        db.add(
            OrgSsoConnection(
                org_id=org.id,
                jackson_tenant=tenant,
                jackson_product=JACKSON_PRODUCT,
                connection_type="saml",
            )
        )
    return connection


def get_login_redirect_url(org: Org, state: str) -> str:
    tenant = str(org.id)
    params = httpx.QueryParams(
        {
            "response_type": "code",
            "client_id": f"tenant={tenant}&product={JACKSON_PRODUCT}",
            "redirect_uri": f"{settings.api_public_url}/identity/callback",
            "state": state,
            "tenant": tenant,
            "product": JACKSON_PRODUCT,
        }
    )
    return f"{settings.jackson_base_url}/api/oauth/authorize?{params}"


def issue_session_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "org_id": str(user.org_id),
        "email": user.email,
        "iat": now,
        "exp": now + SESSION_TTL,
    }
    return jwt.encode(payload, settings.jwt_signing_key, algorithm="HS256")


def get_current_user(token: str | None) -> User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_signing_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None

    with org_scoped_session(payload["org_id"]) as db:
        user = db.get(User, payload["sub"])
        if user is None:
            return None
        db.expunge(user)
        return user


def get_user_roles(user: User) -> dict[str, str]:
    return {"business_role": user.business_role, "system_role": user.system_role}


def _resolve_business_role(db, org_id, idp_group_names: list[str]) -> str | None:
    if not idp_group_names:
        return None
    rows = db.scalars(
        select(IdpGroupRoleMap).where(
            IdpGroupRoleMap.org_id == org_id,
            IdpGroupRoleMap.idp_group_name.in_(idp_group_names),
        )
    ).all()
    return rows[0].business_role if rows else None


def handle_callback(org: Org, code: str) -> User:
    token_resp = httpx.post(
        f"{settings.jackson_base_url}/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": f"tenant={org.id}&product={JACKSON_PRODUCT}",
            "client_secret": "dummy",
            "redirect_uri": f"{settings.api_public_url}/identity/callback",
        },
        timeout=10,
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]

    profile_resp = httpx.get(
        f"{settings.jackson_base_url}/api/oauth/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    profile_resp.raise_for_status()
    profile = profile_resp.json()

    email = profile["email"]
    idp_subject = profile.get("id") or profile.get("sub")
    idp_groups = profile.get("groups") or profile.get("roles") or []

    with org_scoped_session(str(org.id)) as db:
        user = db.scalars(select(User).where(User.org_id == org.id, User.email == email)).first()
        if user is None:
            user = User(org_id=org.id, email=email, idp_subject=idp_subject)
            db.add(user)
            db.flush()
        else:
            user.idp_subject = idp_subject

        if user.role_source != "manual":
            mapped_role = _resolve_business_role(db, org.id, idp_groups)
            if mapped_role:
                user.business_role = mapped_role

        db.flush()
        db.refresh(user)
        db.expunge(user)
        return user


def handle_scim_webhook(org: Org, payload: dict) -> None:
    """Applies a Jackson Directory Sync event. No local group-membership
    table (see aboutproject.md) - group events recompute business_role
    directly against idp_group_role_map and skip the write if the user's
    role_source is 'manual' (an admin override should not be silently
    clobbered by a sync event, per handoff §4).
    """
    event_type = payload.get("event")
    data = payload.get("data", {})

    if event_type in ("user.created", "user.updated"):
        email = data.get("email")
        if not email:
            return
        with org_scoped_session(str(org.id)) as db:
            user = db.scalars(
                select(User).where(User.org_id == org.id, User.email == email)
            ).first()
            if user is None:
                db.add(User(org_id=org.id, email=email, idp_subject=data.get("id"), active=data.get("active", True)))
            else:
                user.active = data.get("active", user.active)

    elif event_type == "user.deleted":
        email = data.get("email")
        if not email:
            return
        with org_scoped_session(str(org.id)) as db:
            user = db.scalars(
                select(User).where(User.org_id == org.id, User.email == email)
            ).first()
            if user is not None:
                user.active = False

    elif event_type == "group.user_added" or event_type == "group.user_removed":
        group_name = data.get("group", {}).get("name")
        members = data.get("group", {}).get("members", [])
        member_emails = [m.get("email") for m in members if m.get("email")]
        if not group_name or not member_emails:
            return
        with org_scoped_session(str(org.id)) as db:
            role_rows = db.scalars(
                select(IdpGroupRoleMap).where(
                    IdpGroupRoleMap.org_id == org.id,
                    IdpGroupRoleMap.idp_group_name == group_name,
                )
            ).all()
            if not role_rows:
                return
            mapped_role = role_rows[0].business_role
            users = db.scalars(
                select(User).where(User.org_id == org.id, User.email.in_(member_emails))
            ).all()
            for user in users:
                if user.role_source != "manual":
                    user.business_role = mapped_role
