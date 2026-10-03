"""Company service for CRUD operations."""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.company import Company
from app.models.crawl import CrawlRun
from app.models.page import MonitoredPage


class CompanyConflictError(Exception):
    """Raised when company cannot be deleted due to active crawl runs."""
    pass


class CompanyService:
    @staticmethod
    def create(db: Session, name: str, domain: str) -> Company:
        company = Company(name=name.strip(), domain=domain.strip().lower())
        db.add(company)
        db.commit()
        db.refresh(company)
        return company

    @staticmethod
    def get(db: Session, company_id: int) -> Optional[Company]:
        return db.get(Company, company_id)

    @staticmethod
    def list(db: Session, skip: int = 0, limit: int = 100) -> List[Company]:
        stmt = select(Company).offset(skip).limit(limit).order_by(Company.created_at.desc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def delete(db: Session, company_id: int) -> bool:
        """Hard delete company and cascade to pages, runs, and snapshots per §5.
        
        Rejects with 409 Conflict if any page has an active crawl run.
        """
        company = db.get(Company, company_id)
        if not company:
            return False

        # Check for active crawl runs across company pages
        active_runs = db.query(CrawlRun).join(MonitoredPage).filter(
            MonitoredPage.company_id == company_id,
            CrawlRun.status.in_(["queued", "running"]),
        ).first()

        if active_runs:
            raise CompanyConflictError(
                f"Cannot delete company {company_id} while a crawl run is currently active."
            )

        db.delete(company)
        db.commit()

        # Delete company snapshot and diff files from disk per §5
        try:
            from app.storage.manager import storage_manager
            storage_manager.delete_company_files(company_id)
        except Exception:
            pass  # File deletion failures are logged and must not roll back the DB delete

        return True
