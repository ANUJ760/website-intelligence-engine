"""MonitoredPage request and response schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class PageCreate(BaseModel):
    url: str = Field(..., description="Fully qualified page URL (http/https)")
    page_type: str = Field("other", description="Type of page: homepage, pricing, careers, product, integrations, other")
    crawl_interval_hours: int = Field(24, ge=1, le=8760, description="Crawl frequency in hours")


class PageUpdate(BaseModel):
    is_active: Optional[bool] = None
    crawl_interval_hours: Optional[int] = Field(None, ge=1, le=8760)
    page_type: Optional[str] = None


class PageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    url: str
    page_type: str
    crawl_interval_hours: int
    is_active: bool
    last_crawled_at: Optional[datetime] = None
    next_crawl_at: Optional[datetime] = None
    created_at: datetime
