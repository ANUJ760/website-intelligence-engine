"""MonitoredPage service for CRUD and scheduling queries."""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.security import validate_url_syntax
from app.models.page import MonitoredPage
from app.models.company import Company
from app.models.crawl import CrawlRun


class PageService:
    @staticmethod
    def create(
        db: Session,
        company_id: int,
        url: str,
        page_type: str = "other",
        crawl_interval_hours: int = 24,
    ) -> MonitoredPage:
        # Validate company exists
        company = db.get(Company, company_id)
        if not company:
            raise ValueError(f"Company {company_id} does not exist.")

        # Validate URL syntax and security at creation time per §11 and §13
        validate_url_syntax(url)

        now = datetime.now(timezone.utc)
        page = MonitoredPage(
            company_id=company_id,
            url=url.strip(),
            page_type=page_type.lower(),
            crawl_interval_hours=crawl_interval_hours,
            is_active=True,
            next_crawl_at=now,  # Due immediately for baseline crawl
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        return page

    @staticmethod
    def get(db: Session, page_id: int) -> Optional[MonitoredPage]:
        return db.get(MonitoredPage, page_id)

    @staticmethod
    def list_by_company(
        db: Session, company_id: int, skip: int = 0, limit: int = 100
    ) -> List[MonitoredPage]:
        stmt = (
            select(MonitoredPage)
            .filter(MonitoredPage.company_id == company_id)
            .offset(skip)
            .limit(limit)
            .order_by(MonitoredPage.created_at.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def update(
        db: Session,
        page_id: int,
        is_active: Optional[bool] = None,
        crawl_interval_hours: Optional[int] = None,
        page_type: Optional[str] = None,
    ) -> Optional[MonitoredPage]:
        page = db.get(MonitoredPage, page_id)
        if not page:
            return None

        if is_active is not None:
            page.is_active = is_active
        if crawl_interval_hours is not None:
            page.crawl_interval_hours = crawl_interval_hours
        if page_type is not None:
            page.page_type = page_type.lower()

        db.commit()
        db.refresh(page)
        return page

    @staticmethod
    def get_due_pages(
        db: Session, as_of: Optional[datetime] = None, limit: int = 50
    ) -> List[MonitoredPage]:
        """Find active pages due for crawl that do NOT have an active crawl run."""
        ref_time = as_of or datetime.now(timezone.utc)

        # Active pages where next_crawl_at <= ref_time
        # and no active CrawlRun ('queued' or 'running')
        active_subquery = (
            select(CrawlRun.page_id)
            .filter(CrawlRun.status.in_(["queued", "running"]))
            .scalar_subquery()
        )

        stmt = (
            select(MonitoredPage)
            .filter(
                MonitoredPage.is_active == True,
                MonitoredPage.next_crawl_at <= ref_time,
                ~MonitoredPage.id.in_(active_subquery),
            )
            .order_by(MonitoredPage.next_crawl_at.asc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())
