"""Tests for database models, SQLite PRAGMAs, foreign keys, cascades, and constraints."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.security import InvalidSchemeError
from app.models.company import Company
from app.models.page import MonitoredPage
from app.models.crawl import CrawlRun
from app.models.snapshot import PageSnapshot
from app.services.company_service import CompanyService, CompanyConflictError
from app.services.page_service import PageService
from app.services.crawl_service import CrawlService, ActiveCrawlRunConflictError


@pytest.fixture
def db_session():
    """Provide a transactional session for testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_sqlite_pragmas_active(db_session: Session):
    """Test that PRAGMA foreign_keys, journal_mode, and busy_timeout are enforced."""
    # Test foreign_keys
    fk_result = db_session.execute(text("PRAGMA foreign_keys")).scalar()
    assert fk_result == 1, "PRAGMA foreign_keys must be ON (1)"

    # Test journal_mode
    journal_mode = db_session.execute(text("PRAGMA journal_mode")).scalar()
    assert str(journal_mode).upper() == "WAL", f"Expected WAL mode, got {journal_mode}"

    # Test busy_timeout
    busy_timeout = db_session.execute(text("PRAGMA busy_timeout")).scalar()
    assert busy_timeout == 5000, f"Expected busy_timeout 5000, got {busy_timeout}"


def test_foreign_key_enforcement(db_session: Session):
    """Inserting a MonitoredPage with a non-existent company_id must fail due to foreign key."""
    orphan_page = MonitoredPage(
        company_id=999999,
        url="https://example.com/orphan",
        page_type="homepage",
    )
    db_session.add(orphan_page)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cascade_delete(db_session: Session):
    """Deleting a company must cascade to pages, crawl runs, and snapshots."""
    # 1. Create company
    company = CompanyService.create(db_session, "Cascade Corp", "cascade.com")
    
    # 2. Create page
    page = PageService.create(db_session, company.id, "https://cascade.com/about")
    
    # 3. Create crawl run
    run = CrawlService.create_crawl_run(db_session, page.id)
    CrawlService.finish_crawl_run(db_session, run.id, status="succeeded", http_status=200)
    
    # 4. Create snapshot
    snapshot = CrawlService.create_snapshot(
        db_session,
        page_id=page.id,
        crawl_run_id=run.id,
        content_hash="abc123hash",
        content_path="snapshots/1/1/1.txt",
        title="About Cascade",
    )
    
    company_id = company.id
    page_id = page.id
    run_id = run.id
    snapshot_id = snapshot.id

    # 5. Delete company
    CompanyService.delete(db_session, company_id)

    # 6. Verify all cascaded rows are removed
    assert db_session.get(Company, company_id) is None
    assert db_session.get(MonitoredPage, page_id) is None
    assert db_session.get(CrawlRun, run_id) is None
    assert db_session.get(PageSnapshot, snapshot_id) is None


def test_active_crawl_deduplication(db_session: Session):
    """A page can have at most ONE active ('queued' or 'running') crawl run."""
    company = CompanyService.create(db_session, "Dedup Corp", "dedup.com")
    page = PageService.create(db_session, company.id, "https://dedup.com/home")

    # 1. First queued crawl run succeeds
    run1 = CrawlService.create_crawl_run(db_session, page.id)
    assert run1.status == "queued"

    # 2. Second queued crawl run on same page must be rejected with ActiveCrawlRunConflictError
    with pytest.raises(ActiveCrawlRunConflictError):
        CrawlService.create_crawl_run(db_session, page.id)

    # 3. Change status of run1 to running; second attempt should still fail
    CrawlService.start_crawl_run(db_session, run1.id)
    with pytest.raises(ActiveCrawlRunConflictError):
        CrawlService.create_crawl_run(db_session, page.id)

    # 4. Finish run1; now a new crawl run can be queued
    CrawlService.finish_crawl_run(db_session, run1.id, status="succeeded")
    run2 = CrawlService.create_crawl_run(db_session, page.id)
    assert run2.id != run1.id

    # Cleanup
    CrawlService.finish_crawl_run(db_session, run2.id, status="succeeded")
    CompanyService.delete(db_session, company.id)


def test_page_url_safety_at_creation(db_session: Session):
    """Unsafe URLs (e.g. file:, ftp:, credentials) must be rejected at page creation."""
    company = CompanyService.create(db_session, "Safety Corp", "safety.com")
    
    with pytest.raises(InvalidSchemeError):
        PageService.create(db_session, company.id, "file:///etc/shadow")

    CompanyService.delete(db_session, company.id)


def test_snapshot_persistence_across_restart():
    """Phase 2 Acceptance criteria: Create records, recreate session/connection, verify persistence."""
    # Session 1: Create company, page, run, snapshot
    session1 = SessionLocal()
    company = CompanyService.create(session1, "Persistent Corp", "persistent.com")
    page = PageService.create(session1, company.id, "https://persistent.com/pricing")
    run = CrawlService.create_crawl_run(session1, page.id)
    CrawlService.finish_crawl_run(session1, run.id, status="succeeded", http_status=200)
    
    snapshot = CrawlService.create_snapshot(
        session1,
        page_id=page.id,
        crawl_run_id=run.id,
        content_hash="persisthash456",
        content_path="snapshots/persistent/pricing/1.txt",
        title="Persistent Pricing",
    )
    saved_company_id = company.id
    saved_page_id = page.id
    saved_snapshot_id = snapshot.id
    session1.close()

    # Session 2: Fresh session simulating backend restart
    session2 = SessionLocal()
    loaded_company = session2.get(Company, saved_company_id)
    loaded_page = session2.get(MonitoredPage, saved_page_id)
    loaded_snapshot = session2.get(PageSnapshot, saved_snapshot_id)

    assert loaded_company is not None
    assert loaded_company.name == "Persistent Corp"
    assert loaded_page is not None
    assert loaded_page.url == "https://persistent.com/pricing"
    assert loaded_snapshot is not None
    assert loaded_snapshot.content_hash == "persisthash456"

    # Cleanup
    CompanyService.delete(session2, saved_company_id)
    session2.close()
