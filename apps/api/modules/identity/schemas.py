from datetime import datetime

from pydantic import BaseModel


class SsoConnectionCreate(BaseModel):
    metadata_url: str | None = None
    metadata_xml: str | None = None


class SsoConnectionStatusOut(BaseModel):
    configured: bool
    connection_type: str | None
    created_at: datetime | None


class SsoConnectionOut(BaseModel):
    tenant: str
    product: str
    idp_metadata_url: str


class UserOut(BaseModel):
    id: str
    email: str
    business_role: str
    system_role: str


class OrgUserOut(BaseModel):
    id: str
    email: str
    business_role: str
    system_role: str
    role_source: str
    active: bool


class UserRoleUpdate(BaseModel):
    business_role: str
    system_role: str


class SuperAdminLogin(BaseModel):
    email: str
    password: str
