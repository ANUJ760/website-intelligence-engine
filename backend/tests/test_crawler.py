"""Unit tests for content extraction, text normalization, and crawler behaviors."""

import pytest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
import httpx

from app.crawler.extractor import normalize_text, extract_content, ExtractedContent
from app.crawler.robots import PolitenessManager
from app.crawler.fetcher import HttpCrawler, CrawlResult


def test_text_normalization():
    raw = "  Hello   World! \r\n\r\n\r\n  Enterprise  Solutions\t\tPlatform \n\n\n\n\nContact: $99/mo   "
    normalized = normalize_text(raw)
    expected = "Hello World!\n\nEnterprise Solutions Platform\n\nContact: $99/mo"
    assert normalized == expected


def test_unicode_normalization():
    # NFKC normalizes full-width characters and ligatures
    raw = "ＡＢＣ ﬁ 123"
    normalized = normalize_text(raw)
    assert normalized == "ABC fi 123"


def test_extract_content_with_title_and_main_text():
    html = """<!DOCTYPE html>
    <html>
    <head><title>Test Company Inc.</title><link rel="canonical" href="https://example.com/canonical"></head>
    <body>
    <nav><a href="/">Home</a></nav>
    <main>
    <h1>New Cloud Analytics</h1>
    <p>Announcing our new automated cloud intelligence analytics platform.</p>
    <p>Pricing starts at $50 per user per month.</p>
    </main>
    <footer>Copyright 2026</footer>
    </body>
    </html>"""
    extracted = extract_content(html, url="https://example.com")
    assert extracted.title == "Test Company Inc."
    assert extracted.canonical_url == "https://example.com/canonical"
    assert "New Cloud Analytics" in extracted.text
    assert "$50 per user per month" in extracted.text
    assert extracted.raw_size_bytes > 0


def test_extract_content_fallback_bs4():
    # Page with minimal markup where trafilatura might not find main text
    html = "<div>Simple minimal snippet text content</div>"
    extracted = extract_content(html)
    assert "Simple minimal snippet text content" in extracted.text


def test_robots_txt_disallow_honored():
    manager = PolitenessManager()
    robots_content = """
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /public/
"""
    manager.parse_robots_txt("https://example.com", robots_content, "WebsiteIntelligenceEngine")
    
    assert manager.is_allowed("https://example.com/public/page", "WebsiteIntelligenceEngine") is True
    assert manager.is_allowed("https://example.com/admin/settings", "WebsiteIntelligenceEngine") is False
    assert manager.is_allowed("https://example.com/private/data", "WebsiteIntelligenceEngine") is False


@pytest.mark.asyncio
async def test_crawler_rejects_ssrf_before_fetch():
    crawler = HttpCrawler()
    result = await crawler.crawl("http://127.0.0.1:8000/secret")
    assert result.success is False
    assert result.error_code == "SSRF_VIOLATION"


@pytest.mark.asyncio
async def test_crawler_rejects_disallowed_scheme():
    crawler = HttpCrawler()
    result = await crawler.crawl("file:///etc/passwd")
    assert result.success is False
    assert result.error_code == "SSRF_VIOLATION"


@pytest.mark.asyncio
async def test_crawler_rejects_disallowed_port():
    crawler = HttpCrawler()
    result = await crawler.crawl("http://example.com:22")
    assert result.success is False
    assert result.error_code == "SSRF_VIOLATION"


@pytest.mark.asyncio
async def test_crawler_successful_fetch():
    crawler = HttpCrawler()
    html_content = "<html><head><title>Mocked Page</title></head><body><h1>Hello World</h1><p>Welcome to Acme Corp.</p></body></html>"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.encoding = "utf-8"
    
    async def aiter_bytes():
        yield html_content.encode("utf-8")
        
    mock_response.aiter_bytes = aiter_bytes
    
    class MockStreamContext:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("app.crawler.fetcher.validate_url", return_value=("https://example.com", "93.184.215.14")), \
         patch("app.crawler.fetcher.PinnedTransport"), \
         patch("app.crawler.fetcher.politeness_manager.enforce_politeness"), \
         patch("app.crawler.fetcher.HttpCrawler.fetch_robots_txt"), \
         patch.object(httpx.AsyncClient, "stream", return_value=MockStreamContext()):
        
        result = await crawler.crawl("https://example.com")
        assert result.success is True
        assert result.status_code == 200
        assert result.title == "Mocked Page"
        assert "Welcome to Acme Corp." in result.extracted_text
        assert len(result.content_hash) == 64  # SHA-256


@pytest.mark.asyncio
async def test_crawler_oversized_response():
    crawler = HttpCrawler(max_response_bytes=100)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    
    async def aiter_bytes():
        yield b"A" * 80
        yield b"B" * 80
        
    mock_response.aiter_bytes = aiter_bytes
    
    class MockStreamContext:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("app.crawler.fetcher.validate_url", return_value=("https://example.com", "93.184.215.14")), \
         patch("app.crawler.fetcher.PinnedTransport"), \
         patch("app.crawler.fetcher.politeness_manager.enforce_politeness"), \
         patch("app.crawler.fetcher.HttpCrawler.fetch_robots_txt"), \
         patch.object(httpx.AsyncClient, "stream", return_value=MockStreamContext()):
        
        result = await crawler.crawl("https://example.com")
        assert result.success is False
        assert result.error_code == "RESPONSE_TOO_LARGE"


@pytest.mark.asyncio
async def test_crawler_unsupported_content_type():
    crawler = HttpCrawler()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/pdf"}
    
    class MockStreamContext:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("app.crawler.fetcher.validate_url", return_value=("https://example.com", "93.184.215.14")), \
         patch("app.crawler.fetcher.PinnedTransport"), \
         patch("app.crawler.fetcher.politeness_manager.enforce_politeness"), \
         patch("app.crawler.fetcher.HttpCrawler.fetch_robots_txt"), \
         patch.object(httpx.AsyncClient, "stream", return_value=MockStreamContext()):
        
        result = await crawler.crawl("https://example.com")
        assert result.success is False
        assert result.error_code == "UNSUPPORTED_CONTENT_TYPE"
