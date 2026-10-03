"""Unit and integration tests for Celery tasks, scheduling, deduplication, and stale recovery."""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.crawler.fetcher import CrawlResult
from app.models.crawl import CrawlRun
from app.models.page import MonitoredPage
from app.services.company_service import CompanyService
from app.services.page_service import PageService
from app.services.crawl_service import CrawlService
from app.tasks.crawl_tasks import (
    crawl_page_task,
    classify_change_task,
    schedule_due_pages_task,
    recover_stale_runs_task,
)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_crawl_page_task_execution(db_session: Session):
    """Test manual crawl_page_task execution outside HTTP request."""
    company = CompanyService.create(db_session, "Task Corp", "task.com")
    page = PageService.create(db_session, company.id, "https://task.com/news")

    mock_crawl_result = CrawlResult(
        url=page.url,
        final_url=page.url,
        status_code=200,
        success=True,
        title="Task News",
        extracted_text="Task News Content: Version 1",
        content_hash="taskhash1",
    )

    with patch("app.crawler.fetcher.HttpCrawler.crawl", return_value=mock_crawl_result):
        # Run task synchronously (e.g. celery worker or direct call)
        res = crawl_page_task(page.id)
        assert res["status"] == "success"
        assert res["page_id"] == page.id

    # Verify run succeeded in DB
    run = db_session.get(CrawlRun, res["crawl_run_id"])
    assert run is not None
    assert run.status == "succeeded"

    # Cleanup
    CompanyService.delete(db_session, company.id)


def test_duplicate_crawl_prevention(db_session: Session):
    """Phase 7 Acceptance: Two simultaneous requests to crawl the same page produce only ONE active run."""
    company = CompanyService.create(db_session, "Simult Corp", "simult.com")
    page = PageService.create(db_session, company.id, "https://simult.com/features")

    # First task creates active run and starts running
    run1 = CrawlService.create_crawl_run(db_session, page.id)
    assert run1.status == "queued"

    # Second task attempt without pre-created run ID detects active run and skips safely
    res2 = crawl_page_task(page.id)
    assert res2["status"] == "skipped"
    assert "Active crawl run exists" in res2["message"]

    # Verify only ONE active run exists in DB
    active_runs = (
        db_session.query(CrawlRun)
        .filter(CrawlRun.page_id == page.id, CrawlRun.status.in_(["queued", "running"]))
        .all()
    )
    assert len(active_runs) == 1

    # Cleanup
    CrawlService.finish_crawl_run(db_session, run1.id, status="succeeded")
    CompanyService.delete(db_session, company.id)


def test_schedule_due_pages_task(db_session: Session):
    """Test Beat scheduler task enqueuing due pages."""
    company = CompanyService.create(db_session, "Due Corp", "due.com")
    page1 = PageService.create(db_session, company.id, "https://due.com/p1")
    page2 = PageService.create(db_session, company.id, "https://due.com/p2")

    # Set page1 due in past, page2 due in future
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    future = datetime.now(timezone.utc) + timedelta(hours=24)
    page1.next_crawl_at = past
    page2.next_crawl_at = future
    db_session.commit()

    with patch("app.tasks.crawl_tasks.crawl_page_task.delay") as mock_delay:
        result = schedule_due_pages_task()
        assert result["enqueued"] == 1
        mock_delay.assert_called_once()

    # Mark enqueued run finished before company deletion per §5 policy
    active_runs = (
        db_session.query(CrawlRun)
        .join(MonitoredPage)
        .filter(MonitoredPage.company_id == company.id)
        .all()
    )
    for r in active_runs:
        r.status = "succeeded"
    db_session.commit()

    CompanyService.delete(db_session, company.id)


def test_recover_stale_runs_task(db_session: Session):
    """Test that stalled 'running' runs older than threshold are marked failed."""
    company = CompanyService.create(db_session, "Stale Corp", "stale.com")
    page = PageService.create(db_session, company.id, "https://stale.com/stale-page")

    # Create run that has been 'running' for 30 minutes
    run = CrawlService.create_crawl_run(db_session, page.id)
    run.status = "running"
    run.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    db_session.commit()

    # Run recovery with 15 min threshold
    result = recover_stale_runs_task(stale_threshold_minutes=15)
    assert result["recovered"] >= 1

    db_session.refresh(run)
    assert run.status == "failed"
    assert run.error_code == "STALE_TIMEOUT"

    CompanyService.delete(db_session, company.id)
