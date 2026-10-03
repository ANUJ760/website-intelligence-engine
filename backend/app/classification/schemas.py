"""Pydantic schemas and controlled vocabulary for AI signal classification."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SignalType(str, Enum):
    PRODUCT_LAUNCH = "PRODUCT_LAUNCH"
    PRICING_CHANGE = "PRICING_CHANGE"
    HIRING_EXPANSION = "HIRING_EXPANSION"
    MARKET_EXPANSION = "MARKET_EXPANSION"
    NEW_INTEGRATION = "NEW_INTEGRATION"
    POSITIONING_CHANGE = "POSITIONING_CHANGE"
    OTHER = "OTHER"
    NO_SIGNAL = "NO_SIGNAL"


class SignalClassificationOutput(BaseModel):
    """Schema-validated classifier output per §9."""
    change_type: SignalType
    observed_change: str = Field(
        ...,
        description="Fact-based statement of what the page demonstrably says or changed.",
    )
    potential_business_signal: str = Field(
        ...,
        description="Inferred business implication (must be clearly distinguished from facts).",
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="Exact quote(s) or excerpt(s) directly from the supplied page content or diff.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Heuristic confidence score (not a calibrated probability).",
    )
