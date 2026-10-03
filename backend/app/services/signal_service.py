"""SignalService for orchestrating AI signal classification and DB persistence."""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.classification.base import get_classifier
from app.classification.prompts import PROMPT_VERSION
from app.config import settings
from app.models.change import ChangeEvent
from app.models.company import Company
from app.models.page import MonitoredPage
from app.models.signal import BusinessSignal
from app.models.snapshot import PageSnapshot
from app.storage.manager import storage_manager

logger = logging.getLogger(__name__)


class SignalService:
    @staticmethod
    async def classify_and_record(
        db: Session,
        change_event_id: int,
    ) -> Optional[BusinessSignal]:
        """Classify a ChangeEvent and persist the resulting BusinessSignal."""
        change_event = db.get(ChangeEvent, change_event_id)
        if not change_event:
            logger.warning(f"ChangeEvent {change_event_id} not found.")
            return None

        # Check if already classified (unique on change_event_id per §5)
        existing = db.query(BusinessSignal).filter(
            BusinessSignal.change_event_id == change_event_id
        ).first()
        if existing:
            return existing

        page = db.get(MonitoredPage, change_event.page_id)
        if not page:
            return None

        company = db.get(Company, page.company_id)
        if not company:
            return None

        current_snap = db.get(PageSnapshot, change_event.current_snapshot_id)
        if not current_snap:
            return None

        # Load diff text and current text from storage
        diff_text = ""
        current_text = ""
        if change_event.diff_path:
            try:
                diff_text = storage_manager.read_diff_text(change_event.diff_path)
            except Exception as e:
                logger.error(f"Could not read diff file: {e}")

        try:
            current_text = storage_manager.read_snapshot_text(current_snap.content_path)
        except Exception as e:
            logger.error(f"Could not read snapshot file: {e}")

        classifier = get_classifier()
        model_name = getattr(classifier, "model", "rule-based-v1")

        result = await classifier.classify(
            company_name=company.name,
            domain=company.domain,
            url=page.url,
            page_type=page.page_type,
            diff_text=diff_text,
            current_text=current_text,
        )

        signal = BusinessSignal(
            company_id=company.id,
            page_id=page.id,
            change_event_id=change_event.id,
            signal_type=result.change_type.value,
            observed_change=result.observed_change,
            potential_implication=result.potential_business_signal,
            evidence=result.evidence,
            confidence=result.confidence,
            classification_status="success",
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)

        return signal

    @staticmethod
    def get(db: Session, signal_id: int) -> Optional[BusinessSignal]:
        return db.get(BusinessSignal, signal_id)

    @staticmethod
    def list_by_company(
        db: Session, company_id: int, skip: int = 0, limit: int = 100
    ) -> List[BusinessSignal]:
        stmt = (
            select(BusinessSignal)
            .filter(BusinessSignal.company_id == company_id)
            .offset(skip)
            .limit(limit)
            .order_by(BusinessSignal.created_at.desc())
        )
        return list(db.scalars(stmt).all())
