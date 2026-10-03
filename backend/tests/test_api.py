"""API endpoint integration tests using FastAPI TestClient."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.core.database import SessionLocal
from app.main import app
from app.models.crawl import CrawlRun
from app.services.company_service import CompanyService
from app.services.page_service import PageService

client = TestClient(app)


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_company_crud_lifecycle():
    # 1. Register company
    create_resp = client.post(
        "/companies",
        json={"name": "API Test Corp", "domain": "apitest.com"},
    )
    assert create_resp.status_code == 201
    company = create_resp.json()
    comp_id = company["id"]
    assert company["name"] == "API Test Corp"
    assert company["domain"] == "apitest.com"

    # 2. List companies
    list_resp = client.get("/companies?skip=0&limit=10")
    assert list_resp.status_code == 200
    companies = list_resp.json()
    assert any(c["id"] == comp_id for c in companies)

    # 3. Get company
    get_resp = client.get(f"/companies/{comp_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == comp_id

    # 4. Add page
    page_resp = client.post(
        f"/companies/{comp_id}/pages",
        json={
            "url": "https://apitest.com/about",
            "page_type": "about",
            "crawl_interval_hours": 12,
        },
    )
    assert page_resp.status_code == 201
    page = page_resp.json()
    page_id = page["id"]
    assert page["url"] == "https://apitest.com/about"

    # 5. Unsafe URL rejected at creation
    unsafe_resp = client.post(
        f"/companies/{comp_id}/pages",
        json={"url": "file:///etc/passwd", "page_type": "other"},
    )
    assert unsafe_resp.status_code == 400
    assert "Unsafe URL" in unsafe_resp.json()["detail"]

    # 6. Update page settings
    patch_resp = client.patch(
        f"/pages/{page_id}",
        json={"crawl_interval_hours": 48, "is_active": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["crawl_interval_hours"] == 48
    assert patch_resp.json()["is_active"] is False

    # 7. Manual crawl trigger and 409 Conflict deduplication
    with patch("app.tasks.crawl_tasks.crawl_page_task.delay"):
        crawl_resp1 = client.post(f"/pages/{page_id}/crawl")
        assert crawl_resp1.status_code == 202
        assert crawl_resp1.json()["status"] == "queued"

        # Immediate second crawl trigger on same page must return 409 Conflict
        crawl_resp2 = client.post(f"/pages/{page_id}/crawl")
        assert crawl_resp2.status_code == 409

    # 8. Deleting company with active crawl run returns 409 Conflict
    del_resp1 = client.delete(f"/companies/{comp_id}")
    assert del_resp1.status_code == 409

    # Mark active run finished so deletion succeeds
    db = SessionLocal()
    run = db.query(CrawlRun).filter(CrawlRun.page_id == page_id).first()
    if run:
        run.status = "succeeded"
        db.commit()
    db.close()

    # 9. Hard delete company
    del_resp2 = client.delete(f"/companies/{comp_id}")
    assert del_resp2.status_code == 204

    # Verify company is gone
    get_gone = client.get(f"/companies/{comp_id}")
    assert get_gone.status_code == 404
