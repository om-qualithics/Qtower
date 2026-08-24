import hashlib
import hmac
import json
import secrets

from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from apps.api.core.rate_limit import RateLimitExceededError, check_rate_limit
from apps.api.core.settings import settings
from apps.api.modules.authz import service as authz_service
from apps.api.modules.identity import service as identity_service
from apps.api.modules.identity.models import User
from apps.api.modules.identity.schemas import (
    OrgUserOut,
    SsoConnectionCreate,
    SsoConnectionStatusOut,
    SuperAdminLogin,
    UserOut,
    UserRoleUpdate,
)
from apps.api.modules.identity.service import IdentityValidationError

router = APIRouter(prefix="/identity", tags=["identity"])


def _verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not signature_header or not settings.jackson_webhook_secret:
        return False
    parts = dict(p.split("=", 1) for p in signature_header.split(","))
    timestamp, signature = parts.get("t"), parts.get("s")
    if not timestamp or not signature:
        return False

    expected = hmac.new(
        settings.jackson_webhook_secret.encode(),
        f"{timestamp}.{raw_body.decode()}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _require_user(session_token: str | None) -> User:
    user = identity_service.get_current_user(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


_STATE_COOKIE_NAME = "misty_login_state"


@router.get("/login")
def login():
    org = identity_service.get_org()
    state = secrets.token_urlsafe(24)
    redirect = RedirectResponse(identity_service.get_login_redirect_url(org, state))
    redirect.set_cookie(
        _STATE_COOKIE_NAME,
        state,
        httponly=True,
        secure=settings.public_hostname != "localhost",
        samesite="lax",
        max_age=300,
    )
    return redirect


@router.get("/callback")
def callback(
    code: str,
    state: str,
    misty_login_state: str | None = Cookie(default=None),
):
    if not misty_login_state or not secrets.compare_digest(state, misty_login_state):
        raise HTTPException(status_code=400, detail="Invalid or expired login state")

    org = identity_service.get_org()
    user = identity_service.handle_callback(org, code)
    token = identity_service.issue_session_token(user)

    redirect = RedirectResponse(f"{settings.web_public_url}/dashboard")
    redirect.delete_cookie(_STATE_COOKIE_NAME)
    redirect.set_cookie(
        identity_service.SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.public_hostname != "localhost",
        samesite="lax",
        max_age=int(identity_service.SESSION_TTL.total_seconds()),
    )
    return redirect


@router.post("/admin/login")
def super_admin_login(body: SuperAdminLogin, request: Request):
    """Break-glass local login - entirely independent of the /login ->
    Jackson -> /callback SAML flow above, so it still works if Jackson or
    the org's SSO connection is broken. Disabled outright (always 401)
    unless SUPER_ADMIN_EMAIL/_PASSWORD_HASH are configured."""
    client_ip = request.client.host if request.client else "unknown"
    try:
        # Password-guessing is the one realistic attack surface this
        # break-glass local-auth path adds beyond SSO - rate-limited by
        # source IP, generously enough to never bother a real operator.
        check_rate_limit(f"admin-login:{client_ip}", limit=10, window_seconds=300)
    except RateLimitExceededError as exc:
        raise HTTPException(status_code=429, detail="Too many login attempts - try again shortly") from exc

    org = identity_service.get_org()
    user = identity_service.authenticate_super_admin(org, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = identity_service.issue_session_token(user)
    response = JSONResponse({"ok": True})
    response.set_cookie(
        identity_service.SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.public_hostname != "localhost",
        samesite="lax",
        max_age=int(identity_service.SESSION_TTL.total_seconds()),
    )
    return response


@router.post("/logout")
def logout():
    redirect = RedirectResponse(f"{settings.web_public_url}/", status_code=303)
    redirect.delete_cookie(identity_service.SESSION_COOKIE_NAME)
    return redirect


@router.get("/me", response_model=UserOut)
def me(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "identity.view_self"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return UserOut(
        id=str(user.id), email=user.email, business_role=user.business_role, system_role=user.system_role
    )


@router.post("/admin/sso-connection")
def create_sso_connection(
    body: SsoConnectionCreate, misty_session: str | None = Cookie(default=None)
):
    user = _require_user(misty_session)
    if not authz_service.can(user, "identity.manage_sso"):
        raise HTTPException(status_code=403, detail="Forbidden")

    org = identity_service.get_org()
    try:
        return identity_service.create_sso_connection(org, body.metadata_url, body.metadata_xml)
    except IdentityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/sso-connection", response_model=SsoConnectionStatusOut)
def get_sso_connection_status(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "identity.manage_sso"):
        raise HTTPException(status_code=403, detail="Forbidden")

    org = identity_service.get_org()
    connection = identity_service.get_sso_connection(org)
    if connection is None:
        return SsoConnectionStatusOut(configured=False, connection_type=None, created_at=None)
    return SsoConnectionStatusOut(
        configured=True, connection_type=connection.connection_type, created_at=connection.created_at
    )


def _to_org_user_out(u: User) -> OrgUserOut:
    return OrgUserOut(
        id=str(u.id), email=u.email, business_role=u.business_role, system_role=u.system_role,
        role_source=u.role_source, active=u.active,
    )


@router.get("/admin/users", response_model=list[OrgUserOut])
def list_org_users(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "identity.manage_users"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    return [_to_org_user_out(u) for u in identity_service.list_org_users(org)]


@router.patch("/admin/users/{user_id}", response_model=OrgUserOut)
def update_user_role(user_id: str, body: UserRoleUpdate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "identity.manage_users"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        updated = identity_service.update_user_role(org, user_id, body.business_role, body.system_role)
    except IdentityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_org_user_out(updated)


@router.post("/scim/webhook")
async def scim_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("BoxyHQ-Signature")
    if not _verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    org = identity_service.get_org()
    payload = json.loads(raw_body)
    if isinstance(payload, list):
        for event in payload:
            identity_service.handle_scim_webhook(org, event)
    else:
        identity_service.handle_scim_webhook(org, payload)
    return {"status": "ok"}
