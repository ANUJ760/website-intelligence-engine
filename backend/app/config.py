import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root is the parent directory of 'backend'
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"

    # Database
    DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT}/data/intelligence.db"

    # Redis broker for Celery
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # Storage paths
    SNAPSHOT_DIR: str = str(BACKEND_DIR / "storage" / "snapshots")
    LOG_DIR: str = str(BACKEND_DIR / "storage" / "logs")
    DIFF_DIR: str = str(BACKEND_DIR / "storage" / "diffs")

    # API binding and CORS
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Crawler settings
    CRAWLER_USER_AGENT: str = "WebsiteIntelligenceEngine/0.1 (+contact: you@example.com)"
    MIN_DOMAIN_DELAY_SECONDS: float = 2.0
    MAX_REDIRECTS: int = 5
    MAX_RESPONSE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    CRAWL_TIMEOUT_SECONDS: float = 15.0
    ALLOWED_PORTS: List[int] = [80, 443]

    # Snapshot retention
    SNAPSHOT_RETENTION_DAYS: Optional[int] = None

    # AI Classification
    AI_CLASSIFICATION_ENABLED: bool = False
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: Optional[str] = "gemini-2.5-flash"


settings = Settings()

# Ensure local directories exist safely
def ensure_directories() -> None:
    Path(settings.SNAPSHOT_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.DIFF_DIR).mkdir(parents=True, exist_ok=True)
    
    # Ensure data dir for sqlite
    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
