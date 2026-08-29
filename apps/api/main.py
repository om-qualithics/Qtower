import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError

from apps.api.core import storage
from apps.api.core.settings import settings
from apps.api.modules.branding.router import router as branding_router
from apps.api.modules.codescan.router import router as codescan_router
from apps.api.modules.dashboard.router import router as dashboard_router
from apps.api.modules.escalations.router import router as escalations_router
from apps.api.modules.identity.router import router as identity_router
from apps.api.modules.licensing.service import sync_license_on_boot
from apps.api.modules.policy.router import router as policy_router
from apps.api.modules.tools.router import router as tools_router
from apps.api.modules.training.router import router as training_router

logger = logging.getLogger(__name__)

_DEV_JWT_SIGNING_KEY = "dev-only-change-me"


def _assert_not_shipping_dev_secrets() -> None:
    """A deployment is only ever "production" once public_hostname is set
    to something real (see identity/router.py's Secure-cookie check, which
    keys off the same field) - if that's true but the JWT signing key is
    still the hardcoded dev default, every session cookie this deployment
    ever issues is forgeable by anyone who reads this repo's source. Fails
    loud (refuses to boot) rather than silently running insecurely, same
    "fail loud, don't silently downgrade" rule AiGatewayConfigError and
    NotificationConfigError already follow elsewhere in this codebase."""
    if settings.public_hostname != "localhost" and settings.jwt_signing_key == _DEV_JWT_SIGNING_KEY:
        raise RuntimeError(
            "Refusing to start: JWT_SIGNING_KEY is still the default dev value while "
            "PUBLIC_HOSTNAME is set to a real host. Set a real, unique JWT_SIGNING_KEY "
            "in this deployment's .env before running against a real hostname."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _assert_not_shipping_dev_secrets()
    sync_license_on_boot()
    storage.ensure_bucket()
    yield


app = FastAPI(title="Q Tower API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_public_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Malformed input this app's own code rejects with a plain
    ValueError (most commonly `uuid.UUID(path_param)` on a path/query
    parameter that isn't a valid UUID) would otherwise surface as an
    unhandled 500 - the client sent a bad request, not something the
    server failed at, so this maps it to a 400 without leaking a
    traceback. Deliberately broad (bare ValueError, not a narrower custom
    type) since ~17 service functions across every module raise it this
    same way for the same reason."""
    logger.info("ValueError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=400, content={"detail": "Invalid request"})


@app.exception_handler(DataError)
async def data_error_handler(request: Request, exc: DataError) -> JSONResponse:
    """Same client-input class as value_error_handler above, one layer
    deeper: a few call sites (e.g. identity_service.update_user_role) pass
    a path param straight to db.get()/a query without a prior
    uuid.UUID(...) conversion, so a malformed id surfaces here as
    Postgres rejecting the literal (psycopg InvalidTextRepresentation)
    instead of as a Python-level ValueError. Still unambiguously "the
    client sent a malformed identifier," never a real server fault, so it
    gets the same 400 treatment rather than a leaked 500."""
    logger.info("DataError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=400, content={"detail": "Invalid request"})

app.include_router(identity_router)
app.include_router(branding_router)
app.include_router(policy_router)
app.include_router(tools_router)
app.include_router(escalations_router)
app.include_router(training_router)
app.include_router(dashboard_router)
app.include_router(codescan_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
