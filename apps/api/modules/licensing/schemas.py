from datetime import datetime

from pydantic import BaseModel


class LicensePayload(BaseModel):
    org_name: str
    seat_count: int
    issued_at: datetime
    expires_at: datetime
    enabled_modules: list[str]
