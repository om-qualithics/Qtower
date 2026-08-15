import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.core.db import Base

BusinessRole = PgEnum("govern", "assure", "operator", name="business_role", create_type=False)
SystemRole = PgEnum("user", "admin", "super_admin", name="system_role", create_type=False)
RoleSource = PgEnum("manual", "synced", name="role_source", create_type=False)
ConnectionType = PgEnum("saml", "oidc", name="sso_connection_type", create_type=False)


class Org(Base):
    __tablename__ = "org"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    users: Mapped[list["User"]] = relationship(back_populates="org")


class User(Base):
    """org_id-scoped table — first proof of the multi-tenant RLS pattern
    every org-scoped table in the platform must follow (see handoff §2.1).
    """

    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    business_role: Mapped[str] = mapped_column(BusinessRole, nullable=False, server_default="operator")
    system_role: Mapped[str] = mapped_column(SystemRole, nullable=False, server_default="user")
    role_source: Mapped[str] = mapped_column(RoleSource, nullable=False, server_default="synced")
    idp_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    org: Mapped["Org"] = relationship(back_populates="users")


class OrgSsoConnection(Base):
    """Maps our org to Jackson's (tenant, product) connection keys. product
    is a fixed constant ("misty") - every org uses the same Jackson
    "product", only tenant varies (= org_id as a string).
    """

    __tablename__ = "org_sso_connection"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False, unique=True)
    jackson_tenant: Mapped[str] = mapped_column(String(255), nullable=False)
    jackson_product: Mapped[str] = mapped_column(String(255), nullable=False, server_default="misty")
    connection_type: Mapped[str] = mapped_column(ConnectionType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class IdpGroupRoleMap(Base):
    __tablename__ = "idp_group_role_map"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)
    idp_group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_role: Mapped[str] = mapped_column(BusinessRole, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
