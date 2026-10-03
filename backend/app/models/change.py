"""ChangeEvent model with snapshot uniqueness constraint."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChangeEvent(Base):
    __tablename__ = "change_events"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(
        Integer,
        ForeignKey("monitored_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_snapshot_id = Column(
        Integer,
        ForeignKey("page_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_snapshot_id = Column(
        Integer,
        ForeignKey("page_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_summary = Column(Text, nullable=False)
    diff_path = Column(String(1024), nullable=True)
    detected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    is_meaningful = Column(Boolean, nullable=True)

    # Relationships
    page = relationship("MonitoredPage")
    previous_snapshot = relationship("PageSnapshot", foreign_keys=[previous_snapshot_id])
    current_snapshot = relationship("PageSnapshot", foreign_keys=[current_snapshot_id])

    __table_args__ = (
        UniqueConstraint(
            "previous_snapshot_id",
            "current_snapshot_id",
            name="uq_change_event_snapshots",
        ),
    )
