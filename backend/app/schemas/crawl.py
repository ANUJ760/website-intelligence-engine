"""CrawlRun and trigger schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CrawlRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    http_status: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class CrawlTriggerResponse(BaseModel):
    crawl_run_id: int
    page_id: int
    status: str
    message: str
