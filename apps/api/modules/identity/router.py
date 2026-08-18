import hashlib
import hmac
import json
import secrets

from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import RedirectResponse

from apps.api.core.settings import settings
from apps.api.modules.authz import service as authz_service
from apps.api.modules.identity import service as identity_service
from apps.api.modules.identity.models import User
from apps.api.modules.identity.schemas import SsoConnectionCreate, UserOut

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
    return identity_service.create_sso_connection(org, body.metadata_url)


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
