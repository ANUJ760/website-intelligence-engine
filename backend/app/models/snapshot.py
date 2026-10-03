"""PageSnapshot model."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PageSnapshot(Base):
    __tablename__ = "page_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(
        Integer,
        ForeignKey("monitored_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    crawl_run_id = Column(
        Integer,
        ForeignKey("crawl_runs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    content_hash = Column(String(64), nullable=False, index=True)
    content_path = Column(String(1024), nullable=False)
    html_path = Column(String(1024), nullable=True)
    title = Column(String(1024), nullable=True)
    captured_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relationships
    page = relationship("MonitoredPage", back_populates="snapshots")
    crawl_run = relationship("CrawlRun", back_populates="snapshot")
