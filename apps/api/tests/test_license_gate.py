from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from apps.api.modules.licensing.service import require_valid_license


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/gated")
    def gated(_: None = Depends(require_valid_license)):
        return {"status": "ok"}

    return app


def test_gated_route_rejects_when_license_invalid(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.api.modules.licensing.service.branding_service.get_config",
        lambda org: None,
    )
    client = TestClient(_build_app())

    resp = client.get("/gated")

    assert resp.status_code == 402


def test_gated_route_allows_when_license_valid(monkeypatch) -> None:
    class _Config:
        license_valid = True

    monkeypatch.setattr(
        "apps.api.modules.licensing.service.branding_service.get_config",
        lambda org: _Config(),
    )
    client = TestClient(_build_app())

    resp = client.get("/gated")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
