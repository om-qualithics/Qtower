"""user roles, org_sso_connection, idp_group_role_map

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    business_role = postgresql.ENUM(
        "govern", "assure", "operator", name="business_role", create_type=False
    )
    system_role = postgresql.ENUM(
        "user", "admin", "super_admin", name="system_role", create_type=False
    )
    role_source = postgresql.ENUM("manual", "synced", name="role_source", create_type=False)
    connection_type = postgresql.ENUM(
        "saml", "oidc", name="sso_connection_type", create_type=False
    )
    business_role.create(op.get_bind(), checkfirst=True)
    system_role.create(op.get_bind(), checkfirst=True)
    role_source.create(op.get_bind(), checkfirst=True)
    connection_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "user",
        sa.Column("business_role", business_role, nullable=False, server_default="operator"),
    )
    op.add_column(
        "user", sa.Column("system_role", system_role, nullable=False, server_default="user")
    )
    op.add_column(
        "user", sa.Column("role_source", role_source, nullable=False, server_default="synced")
    )
    op.add_column("user", sa.Column("idp_subject", sa.String(255), nullable=True))
    op.add_column(
        "user", sa.Column("active", sa.Boolean(), nullable=False, server_default="true")
    )

    op.create_table(
        "org_sso_connection",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False, unique=True),
        sa.Column("jackson_tenant", sa.String(255), nullable=False),
        sa.Column("jackson_product", sa.String(255), nullable=False, server_default="misty"),
        sa.Column("connection_type", connection_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute('ALTER TABLE "org_sso_connection" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "org_sso_connection" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY org_sso_connection_org_isolation ON "org_sso_connection"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )

    op.create_table(
        "idp_group_role_map",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("idp_group_name", sa.String(255), nullable=False),
        sa.Column("business_role", business_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_idp_group_role_map_org_id", "idp_group_role_map", ["org_id"])
    op.execute('ALTER TABLE "idp_group_role_map" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "idp_group_role_map" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY idp_group_role_map_org_isolation ON "idp_group_role_map"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS idp_group_role_map_org_isolation ON "idp_group_role_map"')
    op.drop_index("ix_idp_group_role_map_org_id", table_name="idp_group_role_map")
    op.drop_table("idp_group_role_map")

    op.execute('DROP POLICY IF EXISTS org_sso_connection_org_isolation ON "org_sso_connection"')
    op.drop_table("org_sso_connection")

    op.drop_column("user", "active")
    op.drop_column("user", "idp_subject")
    op.drop_column("user", "role_source")
    op.drop_column("user", "system_role")
    op.drop_column("user", "business_role")

    postgresql.ENUM(name="sso_connection_type").drop(op.get_bind())
    postgresql.ENUM(name="role_source").drop(op.get_bind())
    postgresql.ENUM(name="system_role").drop(op.get_bind())
    postgresql.ENUM(name="business_role").drop(op.get_bind())
