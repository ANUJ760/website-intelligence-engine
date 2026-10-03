# Website Intelligence Engine

A local-first B2B website monitoring and change-intelligence engine.

## Overview
The application lets a user register companies and public website pages to monitor. It periodically fetches those pages, extracts readable content, stores historical snapshots, detects meaningful changes, and optionally uses an LLM to classify changes into potential business signals.

Built in accordance with [AGENT_BUILD_GUIDE_v2.md](./AGENT_BUILD_GUIDE_v2.md).

## Core Architecture
- **Backend:** Python 3.12 + FastAPI
- **Database:** SQLite with WAL mode, `foreign_keys=ON`, `busy_timeout=5000` via SQLAlchemy + Alembic
- **Crawling:** HTTPX (async, strict SSRF protection, IP pinning, robots.txt politeness) + Playwright (JS rendering)
- **Extraction & Diff:** Trafilatura, BeautifulSoup4, hashlib (SHA-256), difflib
- **Background Tasks:** Celery + Redis (broker) + Celery Beat (scheduler)
- **Frontend:** Next.js + TypeScript + Tailwind CSS (local dashboard)
- **Storage:** Local filesystem (`backend/storage/snapshots/`, `backend/storage/diffs/`, `backend/storage/logs/`)

## Getting Started
See [AGENT_BUILD_GUIDE_v2.md](./AGENT_BUILD_GUIDE_v2.md) for the incremental build specification and phases.
