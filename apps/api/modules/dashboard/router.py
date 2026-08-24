from fastapi import APIRouter, Cookie, HTTPException

from apps.api.modules.authz import service as authz_service
from apps.api.modules.dashboard import service as dashboard_service
from apps.api.modules.dashboard.schemas import DashboardSummaryOut
from apps.api.modules.identity import service as identity_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
def get_summary(misty_session: str | None = Cookie(default=None)):
    user = identity_service.get_current_user(misty_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not authz_service.can(user, "dashboard.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    return dashboard_service.get_summary(org, user)
