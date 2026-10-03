"""BusinessSignal model with unique constraint on change_event_id."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, JSON, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BusinessSignal(Base):
    __tablename__ = "business_signals"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_id = Column(
        Integer,
        ForeignKey("monitored_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_event_id = Column(
        Integer,
        ForeignKey("change_events.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    signal_type = Column(String(50), nullable=False, index=True)
    observed_change = Column(Text, nullable=False)
    potential_implication = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=False)
    confidence = Column(Float, nullable=True)
    classification_status = Column(String(50), default="success", nullable=False)
    model_name = Column(String(100), nullable=True)
    prompt_version = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relationships
    company = relationship("Company")
    page = relationship("MonitoredPage")
    change_event = relationship("ChangeEvent")
