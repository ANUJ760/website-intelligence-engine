"""CrawlRun and PageSnapshot service operations."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.models.crawl import CrawlRun
from app.models.snapshot import PageSnapshot
from app.models.page import MonitoredPage


class ActiveCrawlRunConflictError(Exception):
    """Raised when an active crawl run already exists for a page (409 Conflict)."""
    pass


class CrawlService:
    @staticmethod
    def create_crawl_run(db: Session, page_id: int) -> CrawlRun:
        """Create a queued CrawlRun.
        
        Enforces partial unique index: raises ActiveCrawlRunConflictError if a run is already queued/running.
        """
        page = db.get(MonitoredPage, page_id)
        if not page:
            raise ValueError(f"MonitoredPage {page_id} not found.")

        run = CrawlRun(
            page_id=page_id,
            status="queued",
        )
        db.add(run)
        try:
            db.commit()
            db.refresh(run)
            return run
        except IntegrityError as exc:
            db.rollback()
            raise ActiveCrawlRunConflictError(
                f"Page {page_id} already has an active crawl run queued or running."
            ) from exc

    @staticmethod
    def start_crawl_run(db: Session, crawl_run_id: int) -> Optional[CrawlRun]:
        run = db.get(CrawlRun, crawl_run_id)
        if not run:
            return None
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def finish_crawl_run(
        db: Session,
        crawl_run_id: int,
        status: str,
        http_status: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[CrawlRun]:
        run = db.get(CrawlRun, crawl_run_id)
        if not run:
            return None

        now = datetime.now(timezone.utc)
        run.status = status
        run.finished_at = now
        run.http_status = http_status
        run.error_code = error_code
        run.error_message = error_message

        # Update page crawl timestamps
        page = db.get(MonitoredPage, run.page_id)
        if page:
            page.last_crawled_at = now
            page.next_crawl_at = now + timedelta(hours=page.crawl_interval_hours)

        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def create_snapshot(
        db: Session,
        page_id: int,
        crawl_run_id: int,
        content_hash: str,
        content_path: str,
        html_path: Optional[str] = None,
        title: Optional[str] = None,
    ) -> PageSnapshot:
        snapshot = PageSnapshot(
            page_id=page_id,
            crawl_run_id=crawl_run_id,
            content_hash=content_hash,
            content_path=content_path,
            html_path=html_path,
            title=title,
            captured_at=datetime.now(timezone.utc),
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    @staticmethod
    def get_latest_successful_snapshot(
        db: Session, page_id: int
    ) -> Optional[PageSnapshot]:
        stmt = (
            select(PageSnapshot)
            .join(CrawlRun)
            .filter(
                PageSnapshot.page_id == page_id,
                CrawlRun.status == "succeeded",
            )
            .order_by(PageSnapshot.captured_at.desc())
            .limit(1)
        )
        return db.scalars(stmt).first()
