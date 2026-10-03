"""Detection service: coordinates snapshots, diffing, and ChangeEvent creation."""

from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.crawler.fetcher import CrawlResult
from app.detection.differ import generate_diff, summarize_diff, is_meaningful_change
from app.models.change import ChangeEvent
from app.models.crawl import CrawlRun
from app.models.page import MonitoredPage
from app.models.snapshot import PageSnapshot
from app.services.crawl_service import CrawlService
from app.storage.manager import storage_manager


class DetectionService:
    @staticmethod
    def process_crawl(
        db: Session,
        page_id: int,
        crawl_run_id: int,
        crawl_result: CrawlResult,
    ) -> Tuple[Optional[PageSnapshot], Optional[ChangeEvent]]:
        """Process a crawl result deterministically.
        
        - Failed crawl: marks run failed, never updates baseline snapshot.
        - First crawl: stores baseline snapshot, creates no ChangeEvent.
        - Unchanged crawl (same hash): saves snapshot, creates no ChangeEvent.
        - Changed crawl (diff hash): generates diff, noise check, creates snapshot and ChangeEvent.
        - Order of writes guarantees safety: files written before DB transaction commits.
        """
        # 1. Handle failed crawl
        if not crawl_result.success:
            CrawlService.finish_crawl_run(
                db,
                crawl_run_id,
                status="failed",
                http_status=crawl_result.status_code,
                error_code=crawl_result.error_code,
                error_message=crawl_result.error_message,
            )
            return None, None

        page = db.get(MonitoredPage, page_id)
        if not page:
            raise ValueError(f"MonitoredPage {page_id} not found.")

        # 2. Find latest successful snapshot to compare against
        previous_snapshot = CrawlService.get_latest_successful_snapshot(db, page_id)

        # 3. Write snapshot file to disk first (crash leaves at worst an orphan file)
        snapshot_rel_path = storage_manager.save_snapshot_text(
            company_id=page.company_id,
            page_id=page_id,
            snapshot_id=crawl_run_id,
            text_content=crawl_result.extracted_text,
        )

        # 4. Check if baseline (first successful crawl)
        if previous_snapshot is None:
            snapshot = CrawlService.create_snapshot(
                db,
                page_id=page_id,
                crawl_run_id=crawl_run_id,
                content_hash=crawl_result.content_hash,
                content_path=snapshot_rel_path,
                title=crawl_result.title,
            )
            CrawlService.finish_crawl_run(
                db,
                crawl_run_id,
                status="succeeded",
                http_status=crawl_result.status_code,
            )
            return snapshot, None

        # 5. Check if content hash is identical
        if previous_snapshot.content_hash == crawl_result.content_hash:
            snapshot = CrawlService.create_snapshot(
                db,
                page_id=page_id,
                crawl_run_id=crawl_run_id,
                content_hash=crawl_result.content_hash,
                content_path=snapshot_rel_path,
                title=crawl_result.title,
            )
            CrawlService.finish_crawl_run(
                db,
                crawl_run_id,
                status="succeeded",
                http_status=crawl_result.status_code,
            )
            return snapshot, None

        # 6. Content changed: generate diff and evaluate noise
        previous_text = storage_manager.read_snapshot_text(previous_snapshot.content_path)
        diff_text = generate_diff(previous_text, crawl_result.extracted_text)
        meaningful = is_meaningful_change(
            diff_text=diff_text,
            previous_text=previous_text,
            current_text=crawl_result.extracted_text,
        )
        summary = summarize_diff(diff_text)

        # Save diff file to disk
        diff_rel_path = storage_manager.save_diff_text(
            change_event_id=crawl_run_id,
            diff_content=diff_text,
        )

        # Write snapshot and ChangeEvent atomically in DB
        snapshot = CrawlService.create_snapshot(
            db,
            page_id=page_id,
            crawl_run_id=crawl_run_id,
            content_hash=crawl_result.content_hash,
            content_path=snapshot_rel_path,
            title=crawl_result.title,
        )

        change_event = ChangeEvent(
            page_id=page_id,
            previous_snapshot_id=previous_snapshot.id,
            current_snapshot_id=snapshot.id,
            change_summary=summary,
            diff_path=diff_rel_path,
            is_meaningful=meaningful,
        )
        db.add(change_event)

        CrawlService.finish_crawl_run(
            db,
            crawl_run_id,
            status="succeeded",
            http_status=crawl_result.status_code,
        )
        db.commit()
        db.refresh(change_event)

        return snapshot, change_event
