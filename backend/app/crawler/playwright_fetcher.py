"""Playwright browser crawler with route interception, SSRF protection,
resource blocking, and concurrency limits.
"""

import asyncio
from datetime import datetime, timezone
import hashlib
import logging
from typing import List, Optional
from urllib.parse import urlsplit

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Route, Request

from app.config import settings
from app.core.security import validate_url, SSRFError
from app.crawler.extractor import extract_content
from app.crawler.fetcher import CrawlResult, RobotsDisallowedError
from app.crawler.robots import politeness_manager

logger = logging.getLogger(__name__)

BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}


class PlaywrightCrawler:
    """Headless browser crawler for JavaScript-heavy pages."""

    def __init__(
        self,
        max_concurrency: int = 2,
        timeout_seconds: Optional[float] = None,
        user_agent: Optional[str] = None,
    ):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.timeout_ms = int((timeout_seconds or settings.CRAWL_TIMEOUT_SECONDS) * 1000)
        self.user_agent = user_agent or settings.CRAWLER_USER_AGENT
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()

    async def _get_browser(self) -> Browser:
        async with self._lock:
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            if self._browser is None or not self._browser.is_connected():
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-setuid-sandbox",
                    ],
                )
            return self._browser

    async def close(self) -> None:
        """Close browser instance and stop playwright."""
        async with self._lock:
            if self._browser and self._browser.is_connected():
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

    async def _handle_route(self, route: Route, request: Request, blocked_subresources: List[str]) -> None:
        """Intercept every browser request (subresources, iframes, redirects) to enforce SSRF safety."""
        # 1. Block unnecessary heavy media
        if request.resource_type in BLOCKED_RESOURCE_TYPES:
            await route.abort("blockedbyclient")
            return

        req_url = request.url

        # Allow internal browser data schemes only if safe or required
        if req_url.startswith("data:") or req_url.startswith("blob:"):
            await route.continue_()
            return

        # 2. SSRF and destination IP validation for every subrequest
        try:
            validate_url(req_url)
            await route.continue_()
        except SSRFError as exc:
            logger.warning(f"Blocked unsafe browser subrequest to {req_url}: {exc}")
            blocked_subresources.append(req_url)
            await route.abort("blockedbyclient")
        except Exception as exc:
            logger.warning(f"Aborting subrequest to {req_url} due to validation error: {exc}")
            blocked_subresources.append(req_url)
            await route.abort("blockedbyclient")

    async def crawl(self, url: str) -> CrawlResult:
        """Render and crawl a URL using Playwright with strict safety controls."""
        timestamp = datetime.now(timezone.utc)
        clean_url = url.strip()

        # 1. Pre-validation of main URL
        try:
            _, pinned_ip = validate_url(clean_url)
        except SSRFError as e:
            return CrawlResult(
                url=url,
                final_url=clean_url,
                status_code=0,
                success=False,
                error_code="SSRF_VIOLATION",
                error_message=str(e),
                timestamp=timestamp,
            )

        parsed = urlsplit(clean_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        domain = parsed.hostname or ""

        # 2. Check robots.txt and domain politeness
        if not politeness_manager.is_allowed(clean_url, self.user_agent):
            return CrawlResult(
                url=url,
                final_url=clean_url,
                status_code=0,
                success=False,
                error_code="ROBOTS_DISALLOWED",
                error_message=f"Access to '{clean_url}' is disallowed by robots.txt",
                timestamp=timestamp,
            )

        await politeness_manager.enforce_politeness(domain)

        # 3. Acquire concurrency semaphore and execute browser crawl
        async with self.semaphore:
            browser = await self._get_browser()
            context: Optional[BrowserContext] = None
            page: Optional[Page] = None
            blocked_subresources: List[str] = []

            try:
                context = await browser.new_context(
                    user_agent=self.user_agent,
                    ignore_https_errors=False,
                    java_script_enabled=True,
                    bypass_csp=False,
                )
                page = await context.new_page()

                # Register interception for ALL requests (images, scripts, iframes, redirects)
                await page.route(
                    "**/*",
                    lambda route, req: asyncio.create_task(
                        self._handle_route(route, req, blocked_subresources)
                    ),
                )

                response = await page.goto(
                    clean_url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )

                final_url = page.url
                status_code = response.status if response else 200

                # Wait briefly for dynamic JS frameworks if needed
                await page.wait_for_timeout(500)

                html_content = await page.content()
                extracted = extract_content(html_content, url=final_url)
                content_hash = hashlib.sha256(extracted.text.encode("utf-8")).hexdigest()

                return CrawlResult(
                    url=url,
                    final_url=final_url,
                    status_code=status_code,
                    success=True,
                    title=extracted.title,
                    extracted_text=extracted.text,
                    canonical_url=extracted.canonical_url,
                    content_hash=content_hash,
                    raw_html=html_content,
                    timestamp=timestamp,
                )

            except Exception as exc:
                return CrawlResult(
                    url=url,
                    final_url=clean_url,
                    status_code=0,
                    success=False,
                    error_code="BROWSER_CRAWL_FAILED",
                    error_message=str(exc),
                    timestamp=timestamp,
                )
            finally:
                if page:
                    await page.close()
                if context:
                    await context.close()


playwright_crawler = PlaywrightCrawler()
