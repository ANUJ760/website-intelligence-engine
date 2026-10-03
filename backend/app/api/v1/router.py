"""API v1 master router."""

from fastapi import APIRouter
from app.api.v1.companies import router as companies_router
from app.api.v1.pages import router as pages_router
from app.api.v1.health import router as health_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router)
api_v1_router.include_router(companies_router)
api_v1_router.include_router(pages_router)
