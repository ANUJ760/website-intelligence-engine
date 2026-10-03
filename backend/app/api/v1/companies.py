"""Company and company-nested resource endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import SSRFError
from app.schemas.company import CompanyCreate, CompanyResponse
from app.schemas.page import PageCreate, PageResponse
from app.schemas.signal import BusinessSignalResponse
from app.services.company_service import CompanyService, CompanyConflictError
from app.services.page_service import PageService
from app.services.signal_service import SignalService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    """Register a new company to monitor."""
    return CompanyService.create(db, name=payload.name, domain=payload.domain)


@router.get("", response_model=List[CompanyResponse])
def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List registered companies (paginated)."""
    return CompanyService.list(db, skip=skip, limit=limit)


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, db: Session = Depends(get_db)):
    """Get company details by ID."""
    company = CompanyService.get(db, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found",
        )
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db)):
    """Hard-delete a company and associated pages, runs, snapshots, and local storage files.
    
    Returns 409 Conflict if any page has an active crawl run.
    """
    try:
        deleted = CompanyService.delete(db, company_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company {company_id} not found",
            )
    except CompanyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post("/{company_id}/pages", response_model=PageResponse, status_code=status.HTTP_201_CREATED)
def add_monitored_page(
    company_id: int,
    payload: PageCreate,
    db: Session = Depends(get_db),
):
    """Add a monitored page for a company. Validates submitted URL with shared URL-safety module."""
    try:
        page = PageService.create(
            db=db,
            company_id=company_id,
            url=payload.url,
            page_type=payload.page_type,
            crawl_interval_hours=payload.crawl_interval_hours,
        )
        return page
    except SSRFError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsafe URL: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{company_id}/pages", response_model=List[PageResponse])
def list_company_pages(
    company_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List monitored pages for a company."""
    company = CompanyService.get(db, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return PageService.list_by_company(db, company_id, skip=skip, limit=limit)


@router.get("/{company_id}/signals", response_model=List[BusinessSignalResponse])
def list_company_signals(
    company_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retrieve detected business signals for a company."""
    company = CompanyService.get(db, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return SignalService.list_by_company(db, company_id, skip=skip, limit=limit)
