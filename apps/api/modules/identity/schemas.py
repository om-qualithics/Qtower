from pydantic import BaseModel


class SsoConnectionCreate(BaseModel):
    metadata_url: str


class SsoConnectionOut(BaseModel):
    tenant: str
    product: str
    idp_metadata_url: str


class UserOut(BaseModel):
    id: str
    email: str
    business_role: str
    system_role: str
