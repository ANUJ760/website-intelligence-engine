"""Company request and response schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Company name")
    domain: str = Field(..., min_length=1, max_length=255, description="Company primary domain (e.g. example.com)")


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    domain: str
    created_at: datetime
    updated_at: datetime
