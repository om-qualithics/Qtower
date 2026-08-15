from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.settings import settings
from apps.api.modules.identity.router import router as identity_router

app = FastAPI(title="Project Misty API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_public_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(identity_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
