"""Page history and snapshot schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class SnapshotItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    crawl_run_id: int
    content_hash: str
    title: Optional[str] = None
    captured_at: datetime
    content_text: Optional[str] = None


class ChangeEventItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    previous_snapshot_id: int
    current_snapshot_id: int
    change_summary: str
    is_meaningful: Optional[bool] = None
    detected_at: datetime
    diff_text: Optional[str] = None


class PageHistoryResponse(BaseModel):
    page_id: int
    snapshots: List[SnapshotItem]
    changes: List[ChangeEventItem]
