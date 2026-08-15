from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.settings import settings

app = FastAPI(title="Project Misty API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://{settings.public_hostname}:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
