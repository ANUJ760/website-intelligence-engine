# Website Intelligence Engine

A local-first B2B website monitoring and change-intelligence engine.

The engine lets users register companies and public website pages, periodically fetches those pages, extracts readable content, stores historical snapshots locally, detects meaningful textual changes, and classifies detected differences into structured business signals.

Built strictly in accordance with [AGENT_BUILD_GUIDE_v2.md](./AGENT_BUILD_GUIDE_v2.md).

---

## Architecture Overview

```text
                   LOCAL MACHINE
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Next.js 14 Dashboard (http://localhost:3000)       │
│       │                                             │
│       ▼                                             │
│  FastAPI Backend (http://127.0.0.1:8000)            │
│       │                                             │
│       ├── SQLite Database (WAL mode, FK=ON)         │
│       │                                             │
│       ├── Enqueue Task                              │
│       ▼                                             │
│  Redis Broker (127.0.0.1:6379)                      │
│       │                                             │
│       ▼                                             │
│  Celery Worker                                      │
│       ├── HTTPX Crawler (Async, SSRF-safe, Pinned)  │
│       ├── Playwright Crawler (JS-heavy pages)       │
│       ├── Content Extraction (Trafilatura + BS4)    │
│       ├── Atomic Local Snapshot Storage             │
│       ├── SHA-256 Hashing & Unified Diffs           │
│       └── AI Classification Interface               │
│                                                     │
│  Celery Beat (Periodic Due Page Scheduler)          │
│                                                     │
│  Local Filesystem: backend/storage/ (Snapshots/Diff)│
└─────────────────────────────────────────────────────┘
```

---

## Key Features & Guiding Principles

1. **Facts vs. Inferences:** The engine strictly distinguishes demonstrably observed facts on web pages from inferred business implications. Changes are never labeled as buying intent.
2. **SSRF & DNS Rebinding Protection:** All outbound crawls and subrequests are validated against a shared security module that:
   - Restricts schemes strictly to `http` and `https`.
   - Restricts ports to `80` and `443`.
   - Rejects loopback (`127.0.0.1`), RFC1918 private ranges, cloud metadata (`169.254.169.254`), IPv6 link-local/ULA, CGNAT, and IPv4-mapped IPv6.
   - Resolves hostnames once and pins connections directly to the validated IP to prevent DNS rebinding.
   - Enforces robots.txt politeness and a mandatory 2-second domain delay.
   - Applies the exact same safety controls to browser subresources via Playwright route interception.
3. **Robust Local Storage:** Extracted text snapshots are stored using internal integer IDs (`snapshots/<company_id>/<page_id>/<snapshot_id>.txt`) using atomic file writes (temporary write + `fsync` + atomic rename). Earlier snapshots are never overwritten.
4. **Deterministic Deduplication & Concurrency:** Crawl runs prevent duplicate active executions through an atomic SQLite partial unique index (`WHERE status IN ('queued', 'running')`).
5. **Prompt-Injection Defense:** Untrusted page content is isolated within explicit boundary delimiters (`<untrusted_page_diff>`) and verified against hallucinated evidence before saving.

---

## Local Development Quickstart

### 1. Prerequisites
- **Python:** 3.12+ (tested on Python 3.12.14)
- **Node.js:** 20+ (tested on v24.18.0)
- **Redis:** Running locally on `127.0.0.1:6379` (via Podman/Docker or local service)

To launch Redis using rootless Podman:
```bash
podman run -d --name redis -p 127.0.0.1:6379:6379 redis:7-alpine
```

### 2. Backend Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Run database migrations
alembic -c backend/alembic.ini upgrade head

# Start FastAPI server (bound to 127.0.0.1)
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Interactive OpenAPI documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 3. Background Workers (Celery & Beat)
In separate terminal tabs:
```bash
# Start Celery Worker
source venv/bin/activate
export PYTHONPATH=backend
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2

# Start Celery Beat Scheduler (single instance)
source venv/bin/activate
export PYTHONPATH=backend
celery -A app.tasks.celery_app beat --loglevel=info
```

### 4. Frontend Dashboard Setup
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser to access the dashboard.

---

## Docker & Container Execution

A complete multi-container setup is prepared in [docker-compose.yml](./docker-compose.yml):

```bash
docker compose up -d --build
```

### Host vs. Container Security Note
Inside containers, backend processes bind to `0.0.0.0:8000` to be accessible across container networks. However, all published ports in `docker-compose.yml` are strictly pinned to the host loopback interface (`127.0.0.1:8000`, `127.0.0.1:3000`, `127.0.0.1:6379`). They are never exposed publicly to external networks.

---

## Backup & Disaster Recovery

All application state is stored locally:
- **Relational Data:** `data/intelligence.db`
- **Extracted Snapshots & Diffs:** `backend/storage/`

### Recommended Backup Procedure
Ensure Celery workers are idle or briefly paused before snapshotting SQLite in WAL mode:
```bash
# 1. Vacuum / checkpoint SQLite WAL into a consistent backup file
sqlite3 data/intelligence.db ".backup data/backup_$(date +%Y%m%d).db"

# 2. Archive local snapshots and diffs
tar -czf "storage_backup_$(date +%Y%m%d).tar.gz" backend/storage/
```

---

## Test Suite

The test suite covers SSRF protection, DNS rebinding, crawler edge cases, text extraction, model constraints, partial index deduplication, atomic storage, deterministic diffs, Playwright interception, AI injection defenses, and REST endpoints:

```bash
source venv/bin/activate
pytest backend/tests/ -v
```
All 51 test suites pass without live external website dependencies.
