"""MonitoredPage model."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MonitoredPage(Base):
    __tablename__ = "monitored_pages"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url = Column(String(2048), nullable=False, index=True)
    page_type = Column(String(50), default="other", nullable=False)
    crawl_interval_hours = Column(Integer, default=24, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)
    next_crawl_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="pages")
    crawl_runs = relationship(
        "CrawlRun",
        back_populates="page",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    snapshots = relationship(
        "PageSnapshot",
        back_populates="page",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
