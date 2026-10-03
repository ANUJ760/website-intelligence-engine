"""Page settings, manual crawl trigger, and history endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db
from app.models.change import ChangeEvent
from app.models.page import MonitoredPage
from app.models.snapshot import PageSnapshot
from app.schemas.crawl import CrawlTriggerResponse
from app.schemas.history import PageHistoryResponse, SnapshotItem, ChangeEventItem
from app.schemas.page import PageResponse, PageUpdate
from app.services.crawl_service import CrawlService, ActiveCrawlRunConflictError
from app.services.page_service import PageService
from app.storage.manager import storage_manager
from app.tasks.crawl_tasks import crawl_page_task

router = APIRouter(prefix="/pages", tags=["pages"])


@router.patch("/{page_id}", response_model=PageResponse)
def update_page_settings(
    page_id: int,
    payload: PageUpdate,
    db: Session = Depends(get_db),
):
    """Update page monitoring configuration (interval, active status, page type)."""
    page = PageService.update(
        db,
        page_id,
        is_active=payload.is_active,
        crawl_interval_hours=payload.crawl_interval_hours,
        page_type=payload.page_type,
    )
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )
    return page


@router.post("/{page_id}/crawl", response_model=CrawlTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_manual_crawl(page_id: int, db: Session = Depends(get_db)):
    """Queue a manual crawl for a page.
    
    Returns 409 Conflict if a crawl run is already queued or running for this page.
    Enqueues Celery task outside the API request and returns promptly.
    """
    page = db.get(MonitoredPage, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )

    try:
        # Atomic database guard using partial unique index
        run = CrawlService.create_crawl_run(db, page_id)
        # Enqueue background task without blocking
        crawl_page_task.delay(page.id, run.id)

        return CrawlTriggerResponse(
            crawl_run_id=run.id,
            page_id=page.id,
            status=run.status,
            message="Manual crawl queued successfully",
        )
    except ActiveCrawlRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get("/{page_id}/history", response_model=PageHistoryResponse)
def get_page_history(page_id: int, db: Session = Depends(get_db)):
    """Retrieve historical snapshots and detected change events with diffs for a page."""
    page = db.get(MonitoredPage, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )

    # 1. Fetch snapshots
    snap_stmt = (
        select(PageSnapshot)
        .filter(PageSnapshot.page_id == page_id)
        .order_by(PageSnapshot.captured_at.desc())
    )
    snapshots_db = db.scalars(snap_stmt).all()

    snapshot_items: List[SnapshotItem] = []
    for s in snapshots_db:
        content_text = None
        try:
            content_text = storage_manager.read_snapshot_text(s.content_path)
        except Exception:
            pass

        snapshot_items.append(
            SnapshotItem(
                id=s.id,
                page_id=s.page_id,
                crawl_run_id=s.crawl_run_id,
                content_hash=s.content_hash,
                title=s.title,
                captured_at=s.captured_at,
                content_text=content_text,
            )
        )

    # 2. Fetch change events
    change_stmt = (
        select(ChangeEvent)
        .filter(ChangeEvent.page_id == page_id)
        .order_by(ChangeEvent.detected_at.desc())
    )
    changes_db = db.scalars(change_stmt).all()

    change_items: List[ChangeEventItem] = []
    for c in changes_db:
        diff_text = None
        if c.diff_path:
            try:
                diff_text = storage_manager.read_diff_text(c.diff_path)
            except Exception:
                pass

        change_items.append(
            ChangeEventItem(
                id=c.id,
                page_id=c.page_id,
                previous_snapshot_id=c.previous_snapshot_id,
                current_snapshot_id=c.current_snapshot_id,
                change_summary=c.change_summary,
                is_meaningful=c.is_meaningful,
                detected_at=c.detected_at,
                diff_text=diff_text,
            )
        )

    return PageHistoryResponse(
        page_id=page.id,
        snapshots=snapshot_items,
        changes=change_items,
    )
