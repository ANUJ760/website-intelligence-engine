"""Asynchronous HTTP crawler with SSRF protection, IP pinning, manual redirects,
robots.txt politeness, streaming size limits, and content extraction.
"""

from datetime import datetime, timezone
import hashlib
from typing import Optional, Set
from urllib.parse import urljoin, urlsplit

import httpx

from app.config import settings
from app.core.security import (
    SSRFError,
    validate_url,
    PinnedTransport,
)
from app.crawler.extractor import ExtractedContent, extract_content
from app.crawler.robots import politeness_manager


class CrawlerError(Exception):
    """Base crawler exception."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ResponseTooLargeError(CrawlerError):
    def __init__(self, size: int, limit: int):
        super().__init__(
            "RESPONSE_TOO_LARGE",
            f"Response exceeded size limit: {size} bytes (max {limit} bytes)",
        )


class DisallowedContentTypeError(CrawlerError):
    def __init__(self, content_type: str):
        super().__init__(
            "UNSUPPORTED_CONTENT_TYPE",
            f"Content-Type '{content_type}' is not supported for text crawling",
        )


class RobotsDisallowedError(CrawlerError):
    def __init__(self, url: str):
        super().__init__(
            "ROBOTS_DISALLOWED",
            f"Access to '{url}' is disallowed by robots.txt",
        )


class TooManyRedirectsError(CrawlerError):
    def __init__(self, hops: int):
        super().__init__(
            "TOO_MANY_REDIRECTS",
            f"Exceeded maximum redirect limit of {hops} hops",
        )


class CrawlResult:
    """Standardized crawl outcome."""

    def __init__(
        self,
        url: str,
        final_url: str,
        status_code: int,
        success: bool,
        title: str = "",
        extracted_text: str = "",
        canonical_url: Optional[str] = None,
        content_hash: str = "",
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        raw_html: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.url = url
        self.final_url = final_url
        self.status_code = status_code
        self.success = success
        self.title = title
        self.extracted_text = extracted_text
        self.canonical_url = canonical_url
        self.content_hash = content_hash
        self.error_code = error_code
        self.error_message = error_message
        self.raw_html = raw_html
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "success": self.success,
            "title": self.title,
            "extracted_text": self.extracted_text,
            "canonical_url": self.canonical_url,
            "content_hash": self.content_hash,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


ALLOWED_CONTENT_PREFIXES = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
    "text/xml",
    "application/xml",
)


class HttpCrawler:
    """Secure, polite HTTP crawler."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        max_redirects: Optional[int] = None,
        max_response_bytes: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.user_agent = user_agent or settings.CRAWLER_USER_AGENT
        self.max_redirects = (
            max_redirects if max_redirects is not None else settings.MAX_REDIRECTS
        )
        self.max_response_bytes = (
            max_response_bytes
            if max_response_bytes is not None
            else settings.MAX_RESPONSE_BYTES
        )
        self.timeout = httpx.Timeout(
            timeout_seconds or settings.CRAWL_TIMEOUT_SECONDS,
            connect=10.0,
            read=15.0,
            write=10.0,
        )

    async def fetch_robots_txt(self, origin: str) -> None:
        """Fetch and cache robots.txt for an origin if not already cached."""
        if politeness_manager.get_cached_parser(origin) is not None:
            return

        robots_url = f"{origin}/robots.txt"
        try:
            _, pinned_ip = validate_url(robots_url)
            transport = PinnedTransport(pinned_ip)
            async with httpx.AsyncClient(
                transport=transport,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
            ) as client:
                resp = await client.get(robots_url)
                if resp.status_code == 200:
                    politeness_manager.parse_robots_txt(origin, resp.text, self.user_agent)
                else:
                    politeness_manager.set_cached_parser(origin, None, None)
        except Exception:
            # If robots.txt cannot be fetched or fails validation, record empty
            politeness_manager.set_cached_parser(origin, None, None)

    async def crawl(self, url: str) -> CrawlResult:
        """Execute a secure crawl for the given URL."""
        current_url = url.strip()
        visited_urls: Set[str] = set()
        hops = 0
        timestamp = datetime.now(timezone.utc)

        try:
            while True:
                if hops > self.max_redirects:
                    raise TooManyRedirectsError(self.max_redirects)

                if current_url in visited_urls:
                    raise CrawlerError("CIRCULAR_REDIRECT", f"Circular redirect detected at {current_url}")
                visited_urls.add(current_url)

                # 1. SSRF and URL validation with connection pinning
                try:
                    _, pinned_ip = validate_url(current_url)
                except SSRFError as e:
                    return CrawlResult(
                        url=url,
                        final_url=current_url,
                        status_code=0,
                        success=False,
                        error_code="SSRF_VIOLATION",
                        error_message=str(e),
                        timestamp=timestamp,
                    )

                parsed = urlsplit(current_url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                domain = parsed.hostname or ""

                # 2. Robots.txt check
                await self.fetch_robots_txt(origin)
                if not politeness_manager.is_allowed(current_url, self.user_agent):
                    raise RobotsDisallowedError(current_url)

                # 3. Domain rate-limiting politeness delay
                await politeness_manager.enforce_politeness(domain)

                # 4. Fetch with pinned IP transport
                transport = PinnedTransport(pinned_ip)
                headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                }

                async with httpx.AsyncClient(
                    transport=transport,
                    timeout=self.timeout,
                    follow_redirects=False,
                ) as client:
                    async with client.stream("GET", current_url, headers=headers) as response:
                        status_code = response.status_code

                        # Check for redirect status codes
                        if status_code in (301, 302, 303, 307, 308):
                            location = response.headers.get("location")
                            if not location:
                                raise CrawlerError("INVALID_REDIRECT", f"Redirect response {status_code} missing Location header")
                            current_url = urljoin(current_url, location.strip())
                            hops += 1
                            continue

                        # Check content-type
                        content_type = response.headers.get("content-type", "").lower()
                        if content_type and not any(content_type.startswith(prefix) for prefix in ALLOWED_CONTENT_PREFIXES):
                            raise DisallowedContentTypeError(content_type)

                        # Stream response body with size limit
                        body_chunks = []
                        total_bytes = 0
                        async for chunk in response.aiter_bytes():
                            total_bytes += len(chunk)
                            if total_bytes > self.max_response_bytes:
                                raise ResponseTooLargeError(total_bytes, self.max_response_bytes)
                            body_chunks.append(chunk)

                        raw_bytes = b"".join(body_chunks)
                        encoding = response.encoding or "utf-8"
                        try:
                            html_text = raw_bytes.decode(encoding, errors="replace")
                        except Exception:
                            html_text = raw_bytes.decode("utf-8", errors="replace")

                        if status_code >= 400:
                            return CrawlResult(
                                url=url,
                                final_url=current_url,
                                status_code=status_code,
                                success=False,
                                error_code=f"HTTP_{status_code}",
                                error_message=f"Server returned HTTP status {status_code}",
                                raw_html=html_text,
                                timestamp=timestamp,
                            )

                        # Extract main content and metadata
                        extracted = extract_content(html_text, url=current_url)
                        content_hash = hashlib.sha256(extracted.text.encode("utf-8")).hexdigest()

                        return CrawlResult(
                            url=url,
                            final_url=current_url,
                            status_code=status_code,
                            success=True,
                            title=extracted.title,
                            extracted_text=extracted.text,
                            canonical_url=extracted.canonical_url,
                            content_hash=content_hash,
                            raw_html=html_text,
                            timestamp=timestamp,
                        )

        except CrawlerError as e:
            return CrawlResult(
                url=url,
                final_url=current_url,
                status_code=0,
                success=False,
                error_code=e.code,
                error_message=e.message,
                timestamp=timestamp,
            )
        except httpx.TimeoutException as e:
            return CrawlResult(
                url=url,
                final_url=current_url,
                status_code=0,
                success=False,
                error_code="TIMEOUT",
                error_message=f"Request timed out: {e}",
                timestamp=timestamp,
            )
        except httpx.RequestError as e:
            return CrawlResult(
                url=url,
                final_url=current_url,
                status_code=0,
                success=False,
                error_code="REQUEST_ERROR",
                error_message=f"Network request error: {e}",
                timestamp=timestamp,
            )
        except Exception as e:
            return CrawlResult(
                url=url,
                final_url=current_url,
                status_code=0,
                success=False,
                error_code="UNEXPECTED_ERROR",
                error_message=str(e),
                timestamp=timestamp,
            )
