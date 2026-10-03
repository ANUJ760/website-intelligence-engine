"""Unit tests for Playwright browser crawler, SSRF interception, and resource blocking."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.crawler.playwright_fetcher import PlaywrightCrawler, BLOCKED_RESOURCE_TYPES
from app.core.security import SSRFError, PrivateIPError


@pytest.mark.asyncio
async def test_playwright_blocks_unnecessary_resources():
    crawler = PlaywrightCrawler()
    
    for res_type in ["image", "media", "font"]:
        mock_route = AsyncMock()
        mock_request = MagicMock()
        mock_request.resource_type = res_type
        mock_request.url = "https://example.com/asset.png"

        blocked = []
        await crawler._handle_route(mock_route, mock_request, blocked)
        mock_route.abort.assert_awaited_with("blockedbyclient")
        mock_route.continue_.assert_not_awaited()


@pytest.mark.asyncio
async def test_playwright_blocks_private_subresources():
    """Verify that iframes or subresources pointing at private/loopback IPs are aborted."""
    crawler = PlaywrightCrawler()
    
    unsafe_suburls = [
        "http://127.0.0.1:8080/admin/api",
        "http://localhost:3000/keys",
        "http://169.254.169.254/latest/meta-data/",
        "http://192.168.1.1/router",
        "file:///etc/passwd",
    ]

    for unsafe_url in unsafe_suburls:
        mock_route = AsyncMock()
        mock_request = MagicMock()
        mock_request.resource_type = "xhr"
        mock_request.url = unsafe_url

        blocked = []
        await crawler._handle_route(mock_route, mock_request, blocked)
        mock_route.abort.assert_awaited_with("blockedbyclient")
        mock_route.continue_.assert_not_awaited()
        assert unsafe_url in blocked


@pytest.mark.asyncio
async def test_playwright_allows_safe_subresources():
    crawler = PlaywrightCrawler()
    mock_route = AsyncMock()
    mock_request = MagicMock()
    mock_request.resource_type = "script"
    mock_request.url = "https://example.com/app.js"

    with patch("app.crawler.playwright_fetcher.validate_url", return_value=("https://example.com/app.js", "93.184.215.14")):
        blocked = []
        await crawler._handle_route(mock_route, mock_request, blocked)
        mock_route.continue_.assert_awaited_once()
        mock_route.abort.assert_not_awaited()
        assert len(blocked) == 0


@pytest.mark.asyncio
async def test_playwright_rejects_ssrf_main_url():
    crawler = PlaywrightCrawler()
    result = await crawler.crawl("http://127.0.0.1:8000/internal")
    assert result.success is False
    assert result.error_code == "SSRF_VIOLATION"
