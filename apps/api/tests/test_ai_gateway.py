import pytest
from sqlalchemy import select

from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.ai_gateway.models import LlmUsageLog
from apps.api.modules.ai_gateway.service import AiGatewayConfigError, complete
from apps.api.modules.identity.models import Org


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


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        db.query(LlmUsageLog).filter(LlmUsageLog.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_mock_provider_round_trip(monkeypatch) -> None:
    # Explicitly pinned rather than relying on Settings' "mock" default -
    # a real deployment's infra/.env sets AI_PROVIDER=live (Milestone 10),
    # and this test must stay hermetic (no real API call) regardless of
    # local env config.
    monkeypatch.setattr("apps.api.modules.ai_gateway.service.settings.ai_provider", "mock")
    org = _make_org("AI Gateway Test Org")
    try:
        response = complete("test_feature", org, "hello")

        assert response.provider == "mock"
        assert "hello" in response.content

        with org_scoped_session(str(org.id)) as db:
            rows = db.scalars(
                select(LlmUsageLog).where(LlmUsageLog.org_id == org.id, LlmUsageLog.feature == "test_feature")
            ).all()
            assert len(rows) == 1
            assert rows[0].provider == "mock"
    finally:
        _delete_org(org)


def test_live_provider_without_api_key_raises_clear_error(monkeypatch) -> None:
    monkeypatch.setattr("apps.api.modules.ai_gateway.service.settings.ai_provider", "live")
    monkeypatch.setattr("apps.api.modules.ai_gateway.service.settings.ai_api_key", "")
    org = _make_org("AI Gateway Config Error Org")
    try:
        with pytest.raises(AiGatewayConfigError):
            complete("test_feature", org, "hello")
    finally:
        _delete_org(org)
