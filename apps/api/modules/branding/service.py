from datetime import datetime

from sqlalchemy import select

from apps.api.core.db import org_scoped_session
from apps.api.modules.branding.models import DeploymentConfig
from apps.api.modules.identity.models import Org


def get_config(org: Org) -> DeploymentConfig | None:
    with org_scoped_session(str(org.id)) as db:
        config = db.scalars(
            select(DeploymentConfig).where(DeploymentConfig.org_id == org.id)
        ).first()
        if config is not None:
            db.expunge(config)
        return config


def update_config(org: Org, fields: dict) -> DeploymentConfig:
    with org_scoped_session(str(org.id)) as db:
        config = db.scalars(
            select(DeploymentConfig).where(DeploymentConfig.org_id == org.id)
        ).first()
        if config is None:
            config = DeploymentConfig(org_id=org.id)
            db.add(config)
            db.flush()

        # `fields` is already `body.model_dump(exclude_unset=True)` from the
        # router - only keys the client actually sent are present at all,
        # so a `None` here means "explicitly clear this field," not "field
        # omitted." Skipping None (as this used to do) made clearing any
        # nullable field - e.g. org_display_name - permanently impossible:
        # the client would send null, it'd be silently ignored, and the
        # old value would just come back on the next GET.
        for key, value in fields.items():
            setattr(config, key, value)

        db.flush()
        db.refresh(config)
        db.expunge(config)
        return config


def upsert_license_result(
    org: Org,
    *,
    valid: bool,
    token: str,
    seat_count: int | None,
    expires_at: datetime | None,
    enabled_modules: list[str] | None,
    validated_at: datetime,
) -> DeploymentConfig:
    with org_scoped_session(str(org.id)) as db:
        config = db.scalars(
            select(DeploymentConfig).where(DeploymentConfig.org_id == org.id)
        ).first()
        if config is None:
            config = DeploymentConfig(org_id=org.id)
            db.add(config)
            db.flush()

        config.license_token = token
        config.license_valid = valid
        config.license_seat_count = seat_count
        config.license_expires_at = expires_at
        config.enabled_feature_modules = enabled_modules
        config.license_validated_at = validated_at

        db.flush()
        db.refresh(config)
        db.expunge(config)
        return config
