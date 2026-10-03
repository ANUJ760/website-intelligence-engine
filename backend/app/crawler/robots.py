"""Robots.txt parsing, caching, and per-domain politeness/rate-limiting."""

import asyncio
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from app.config import settings


class RobotsCacheEntry:
    def __init__(self, parser: Optional[RobotFileParser], crawl_delay: Optional[float], expires_at: float):
        self.parser = parser
        self.crawl_delay = crawl_delay
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class PolitenessManager:
    """Manages domain request delays and robots.txt cache."""

    def __init__(self, default_min_delay: float = 2.0, cache_ttl_seconds: float = 3600.0):
        self.default_min_delay = default_min_delay
        self.cache_ttl_seconds = cache_ttl_seconds
        self._robots_cache: Dict[str, RobotsCacheEntry] = {}
        self._last_access: Dict[str, float] = {}
        self._domain_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_domain_lock(self, domain: str) -> asyncio.Lock:
        async with self._global_lock:
            if domain not in self._domain_locks:
                self._domain_locks[domain] = asyncio.Lock()
            return self._domain_locks[domain]

    def get_cached_parser(self, origin: str) -> Optional[Tuple[Optional[RobotFileParser], Optional[float]]]:
        entry = self._robots_cache.get(origin)
        if entry and not entry.is_expired():
            return entry.parser, entry.crawl_delay
        return None

    def set_cached_parser(self, origin: str, parser: Optional[RobotFileParser], crawl_delay: Optional[float]) -> None:
        self._robots_cache[origin] = RobotsCacheEntry(
            parser=parser,
            crawl_delay=crawl_delay,
            expires_at=time.time() + self.cache_ttl_seconds,
        )

    def parse_robots_txt(self, origin: str, content: str, user_agent: str) -> Tuple[RobotFileParser, Optional[float]]:
        parser = RobotFileParser()
        parser.parse(content.splitlines())
        
        # Check crawl-delay for our user-agent or default wildcard
        crawl_delay = parser.crawl_delay(user_agent)
        if crawl_delay is None:
            crawl_delay = parser.crawl_delay("*")
            
        self.set_cached_parser(origin, parser, crawl_delay)
        return parser, crawl_delay

    def is_allowed(self, url: str, user_agent: str) -> bool:
        """Check if URL is allowed based on cached robots.txt.
        
        If no robots.txt is cached or parsing failed, defaults to True.
        """
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        cached = self.get_cached_parser(origin)
        if not cached or cached[0] is None:
            return True
        
        parser = cached[0]
        return parser.can_fetch(user_agent, url)

    async def enforce_politeness(self, domain: str, explicit_delay: Optional[float] = None) -> None:
        """Enforce delay between requests to the same domain."""
        lock = await self._get_domain_lock(domain)
        async with lock:
            delay = explicit_delay if explicit_delay is not None else self.default_min_delay
            last_time = self._last_access.get(domain, 0.0)
            elapsed = time.time() - last_time
            if elapsed < delay:
                wait_time = delay - elapsed
                await asyncio.sleep(wait_time)
            self._last_access[domain] = time.time()


# Global politeness manager instance
politeness_manager = PolitenessManager(
    default_min_delay=settings.MIN_DOMAIN_DELAY_SECONDS,
)
