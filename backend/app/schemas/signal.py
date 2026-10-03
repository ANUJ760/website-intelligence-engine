"""BusinessSignal response schemas."""

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict


class BusinessSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    page_id: int
    change_event_id: int
    signal_type: str
    observed_change: str
    potential_implication: str
    evidence: List[str]
    confidence: Optional[float] = None
    classification_status: str
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    created_at: datetime
