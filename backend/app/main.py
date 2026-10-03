"""FastAPI Application entrypoint with security, restricted CORS, and OpenAPI docs."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.config import settings, ensure_directories
from app.crawler.playwright_fetcher import playwright_crawler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure data & storage directories exist
    ensure_directories()
    yield
    # Shutdown: cleanly close any active browser contexts
    await playwright_crawler.close()


app = FastAPI(
    title="Website Intelligence Engine API",
    description="Local-first B2B website monitoring and change-intelligence engine.",
    version="0.1.0",
    lifespan=lifespan,
)

# Restrict CORS to dashboard origin per §13 (do NOT use wildcard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers (both under /api/v1 and top-level for convenience)
app.include_router(api_v1_router, prefix="/api/v1")
app.include_router(api_v1_router)


if __name__ == "__main__":
    import uvicorn
    # Enforce binding to 127.0.0.1 per §13
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )
