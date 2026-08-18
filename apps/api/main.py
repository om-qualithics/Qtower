from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core import storage
from apps.api.core.settings import settings
from apps.api.modules.branding.router import router as branding_router
from apps.api.modules.identity.router import router as identity_router
from apps.api.modules.licensing.service import sync_license_on_boot
from apps.api.modules.policy.router import router as policy_router


@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.include_router(identity_router)
app.include_router(branding_router)
app.include_router(policy_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
