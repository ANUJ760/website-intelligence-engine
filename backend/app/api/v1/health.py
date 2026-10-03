"""Application health check endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Basic application and database health check."""
    try:
        db.execute(text("SELECT 1")).scalar()
        db_status = "connected"
    except Exception as exc:
        db_status = f"unhealthy: {exc}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
    }
