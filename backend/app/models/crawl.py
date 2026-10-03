"""CrawlRun model with partial unique index for active crawl deduplication."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import relationship

from app.models.base import Base


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(
        Integer,
        ForeignKey("monitored_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(50), default="queued", nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    http_status = Column(Integer, nullable=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    page = relationship("MonitoredPage", back_populates="crawl_runs")
    snapshot = relationship(
        "PageSnapshot",
        back_populates="crawl_run",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index(
            "uq_active_crawl_per_page",
            "page_id",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
    )
