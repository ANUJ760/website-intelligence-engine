"""Celery task definitions for crawling, classification, scheduling, and stale run recovery."""

import asyncio
from datetime import datetime, timezone, timedelta
import logging
from typing import Optional

from app.config import settings
from app.core.database import SessionLocal
from app.crawler.fetcher import HttpCrawler
from app.models.crawl import CrawlRun
from app.models.page import MonitoredPage
from app.services.crawl_service import CrawlService, ActiveCrawlRunConflictError
from app.services.detection_service import DetectionService
from app.services.page_service import PageService
from app.services.signal_service import SignalService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_coroutine(coro):
    """Run an async coroutine inside Celery synchronous worker."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            return new_loop.run_until_complete(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(
    name="app.tasks.crawl_tasks.crawl_page_task",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    dont_autoretry_for=(ActiveCrawlRunConflictError,),
    retry_backoff=True,
    retry_jitter=True,
)
def crawl_page_task(self, page_id: int, crawl_run_id: Optional[int] = None):
    """Execute fetch, snapshot storage, diffing, and change event detection outside HTTP requests."""
    db = SessionLocal()
    try:
        page = db.get(MonitoredPage, page_id)
        if not page:
            logger.error(f"MonitoredPage {page_id} not found.")
            return {"status": "error", "message": "Page not found"}

        # 1. Deduplication guard: ensure a queued CrawlRun exists
        if crawl_run_id is None:
            try:
                run = CrawlService.create_crawl_run(db, page_id)
                crawl_run_id = run.id
            except ActiveCrawlRunConflictError:
                logger.info(f"Page {page_id} already has an active crawl run. Skipping enqueue.")
                return {"status": "skipped", "message": "Active crawl run exists"}

        # 2. Mark crawl run as running
        CrawlService.start_crawl_run(db, crawl_run_id)

        # 3. Perform network fetch with SSRF and IP pinning
        crawler = HttpCrawler()
        crawl_result = _run_coroutine(crawler.crawl(page.url))

        # 4. Process snapshot, diff, and change event
        snapshot, change_event = DetectionService.process_crawl(
            db=db,
            page_id=page_id,
            crawl_run_id=crawl_run_id,
            crawl_result=crawl_result,
        )

        # 5. If meaningful change detected, trigger separate classification task
        if change_event and change_event.is_meaningful:
            classify_change_task.delay(change_event.id)

        return {
            "status": "success" if crawl_result.success else "failed",
            "page_id": page_id,
            "crawl_run_id": crawl_run_id,
            "change_event_id": change_event.id if change_event else None,
        }

    except Exception as exc:
        logger.exception(f"Unhandled error in crawl_page_task for page {page_id}: {exc}")
        if crawl_run_id:
            CrawlService.finish_crawl_run(
                db,
                crawl_run_id,
                status="failed",
                error_code="WORKER_ERROR",
                error_message=str(exc),
            )
        raise exc
    finally:
        db.close()


@celery_app.task(name="app.tasks.crawl_tasks.classify_change_task")
def classify_change_task(change_event_id: int):
    """Classify a recorded ChangeEvent using configured AI/rule classifier."""
    db = SessionLocal()
    try:
        signal = _run_coroutine(
            SignalService.classify_and_record(db, change_event_id)
        )
        return {
            "status": "success" if signal else "skipped",
            "change_event_id": change_event_id,
            "signal_id": signal.id if signal else None,
        }
    finally:
        db.close()


@celery_app.task(name="app.tasks.crawl_tasks.schedule_due_pages_task")
def schedule_due_pages_task():
    """Beat scheduler task: find active pages due for crawl and enqueue bounded work."""
    db = SessionLocal()
    try:
        # Bounded fetch: max 50 pages per tick to avoid overwhelming workers
        due_pages = PageService.get_due_pages(db, limit=50)
        enqueued_count = 0

        for page in due_pages:
            try:
                # Attempt to create queued run as atomic guard
                run = CrawlService.create_crawl_run(db, page.id)
                crawl_page_task.delay(page.id, run.id)
                enqueued_count += 1
            except ActiveCrawlRunConflictError:
                # Page already has an active run, skip
                continue

        logger.info(f"Scheduled {enqueued_count} due pages for crawling.")
        return {"enqueued": enqueued_count}
    finally:
        db.close()


@celery_app.task(name="app.tasks.crawl_tasks.recover_stale_runs_task")
def recover_stale_runs_task(stale_threshold_minutes: int = 15):
    """Recover stale 'running' CrawlRuns left over after a worker crash or hang."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_threshold_minutes)
        stale_runs = (
            db.query(CrawlRun)
            .filter(
                CrawlRun.status == "running",
                CrawlRun.started_at < cutoff,
            )
            .all()
        )

        recovered_count = len(stale_runs)
        for run in stale_runs:
            run.status = "failed"
            run.error_code = "STALE_TIMEOUT"
            run.error_message = (
                f"Crawl run exceeded {stale_threshold_minutes} minutes without completion."
            )
            run.finished_at = datetime.now(timezone.utc)

        db.commit()
        if recovered_count > 0:
            logger.warning(f"Recovered {recovered_count} stale crawl runs.")
        return {"recovered": recovered_count}
    finally:
        db.close()
