"""Tests for deterministic change detection, diff generation, and ChangeEvent creation."""

import hashlib
import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.crawler.fetcher import CrawlResult
from app.detection.differ import generate_diff, summarize_diff, is_meaningful_change
from app.models.change import ChangeEvent
from app.models.snapshot import PageSnapshot
from app.services.company_service import CompanyService
from app.services.page_service import PageService
from app.services.crawl_service import CrawlService
from app.services.detection_service import DetectionService


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_generate_diff_and_summary():
    text_a = "Acme Corp\nProduct: Basic Plan $10/mo\nFeatures: 5 users"
    text_b = "Acme Corp\nProduct: Enterprise Plan $50/mo\nFeatures: Unlimited users\nNew: 24/7 Support"

    diff = generate_diff(text_a, text_b)
    assert "-Product: Basic Plan $10/mo" in diff
    assert "+Product: Enterprise Plan $50/mo" in diff
    assert "+New: 24/7 Support" in diff

    summary = summarize_diff(diff)
    assert "+3 lines" in summary
    assert "-2 lines" in summary


def test_meaningful_change_noise_filter():
    prev = "Acme Corp home page with products."
    
    # 1. Whitespace only difference -> Not meaningful
    curr_whitespace = "  Acme Corp   home page \nwith  products.  "
    diff1 = generate_diff(prev, curr_whitespace)
    assert not is_meaningful_change(diff1, prev, curr_whitespace)

    # 2. Cookie consent banner addition -> Not meaningful
    curr_cookie = prev + "\nWe use cookies to improve your experience. Accept all cookies."
    diff2 = generate_diff(prev, curr_cookie)
    assert not is_meaningful_change(diff2, prev, curr_cookie)

    # 3. Meaningful content addition -> Meaningful
    curr_product = prev + "\nAnnouncing our new AI-powered website analyzer tool."
    diff3 = generate_diff(prev, curr_product)
    assert is_meaningful_change(diff3, prev, curr_product)


def test_detection_workflow_end_to_end(db_session: Session):
    """Phase 4 Acceptance: Version A to Version B produces correct diff and exactly one change event."""
    company = CompanyService.create(db_session, "Diff Corp", "diff.com")
    page = PageService.create(db_session, company.id, "https://diff.com/pricing")

    # 1. First Crawl (Baseline)
    content_a = "Enterprise Pricing: $99 per user per month."
    hash_a = hashlib.sha256(content_a.encode()).hexdigest()
    result_a = CrawlResult(
        url=page.url,
        final_url=page.url,
        status_code=200,
        success=True,
        title="Diff Corp Pricing",
        extracted_text=content_a,
        content_hash=hash_a,
    )
    run1 = CrawlService.create_crawl_run(db_session, page.id)
    snap1, change1 = DetectionService.process_crawl(db_session, page.id, run1.id, result_a)

    assert snap1 is not None
    assert snap1.content_hash == hash_a
    assert change1 is None, "First crawl must create baseline snapshot, not a change event."

    # 2. Second Crawl (Identical content)
    run2 = CrawlService.create_crawl_run(db_session, page.id)
    snap2, change2 = DetectionService.process_crawl(db_session, page.id, run2.id, result_a)

    assert snap2 is not None
    assert change2 is None, "Identical content must produce no change event."

    # 3. Third Crawl (Failed crawl - 500 error)
    result_fail = CrawlResult(
        url=page.url,
        final_url=page.url,
        status_code=500,
        success=False,
        error_code="HTTP_500",
        error_message="Internal Server Error",
    )
    run3 = CrawlService.create_crawl_run(db_session, page.id)
    snap3, change3 = DetectionService.process_crawl(db_session, page.id, run3.id, result_fail)

    assert snap3 is None
    assert change3 is None
    # Verify latest successful snapshot is still snap2
    latest = CrawlService.get_latest_successful_snapshot(db_session, page.id)
    assert latest.id == snap2.id

    # 4. Fourth Crawl (Version B - Changed content)
    content_b = "Enterprise Pricing: $149 per user per month.\nIncludes AI Copilot add-on."
    hash_b = hashlib.sha256(content_b.encode()).hexdigest()
    result_b = CrawlResult(
        url=page.url,
        final_url=page.url,
        status_code=200,
        success=True,
        title="Diff Corp Pricing",
        extracted_text=content_b,
        content_hash=hash_b,
    )
    run4 = CrawlService.create_crawl_run(db_session, page.id)
    snap4, change4 = DetectionService.process_crawl(db_session, page.id, run4.id, result_b)

    assert snap4 is not None
    assert change4 is not None
    assert change4.previous_snapshot_id == snap2.id
    assert change4.current_snapshot_id == snap4.id
    assert change4.is_meaningful is True
    assert "+1 line" in change4.change_summary or "+2 line" in change4.change_summary

    # 5. Fifth Crawl (Reversion back to Version A)
    # A page that reverts to earlier content still produces a change event
    run5 = CrawlService.create_crawl_run(db_session, page.id)
    snap5, change5 = DetectionService.process_crawl(db_session, page.id, run5.id, result_a)

    assert snap5 is not None
    assert change5 is not None
    assert change5.previous_snapshot_id == snap4.id
    assert change5.current_snapshot_id == snap5.id
    assert change5.is_meaningful is True

    # Cleanup
    CompanyService.delete(db_session, company.id)
