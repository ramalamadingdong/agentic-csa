"""HTTP fetching utilities with caching support."""

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class CacheEntry:
    """A cached HTTP response."""
    
    content: str
    timestamp: float
    headers: dict[str, str] = field(default_factory=dict)


class HttpFetcher:
    """HTTP client with response caching for documentation fetching."""
    
    def __init__(
        self,
        cache_ttl_seconds: int = 3600,
        max_cache_size: int = 1000,
        timeout: float = 30.0,
        user_agent: str = "WPILib-MCP-Server/0.1.0"
    ):
        """
        Initialize the HTTP fetcher.
        
        Args:
            cache_ttl_seconds: How long to cache responses (default: 1 hour)
            max_cache_size: Maximum number of cached responses
            timeout: Request timeout in seconds
            user_agent: User-Agent header for requests
        """
        self.cache_ttl = cache_ttl_seconds
        self.max_cache_size = max_cache_size
        self.timeout = timeout
        self.user_agent = user_agent
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None
    
    def _get_cache_key(self, url: str) -> str:
        """Generate a cache key from URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]
    
    def _is_cache_valid(self, entry: CacheEntry) -> bool:
        """Check if a cache entry is still valid."""
        return (time.time() - entry.timestamp) < self.cache_ttl
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True
            )
        return self._client
    
    async def fetch(self, url: str, use_cache: bool = True) -> str:
        """
        Fetch content from a URL with optional caching.
        
        Args:
            url: The URL to fetch
            use_cache: Whether to use cached responses
            
        Returns:
            The response text content
            
        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        cache_key = self._get_cache_key(url)
        
        # Check cache first
        if use_cache:
            async with self._lock:
                if cache_key in self._cache:
                    entry = self._cache[cache_key]
                    if self._is_cache_valid(entry):
                        return entry.content
        
        # Fetch from network
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        content = response.text
        
        # Store in cache
        if use_cache:
            async with self._lock:
                # Evict old entries if cache is full
                if len(self._cache) >= self.max_cache_size:
                    self._evict_oldest()
                
                self._cache[cache_key] = CacheEntry(
                    content=content,
                    timestamp=time.time(),
                    headers=dict(response.headers)
                )
        
        return content
    
    def _evict_oldest(self) -> None:
        """Remove the oldest cache entry."""
        if not self._cache:
            return
        
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
        del self._cache[oldest_key]
    
    def clear_cache(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()
    
    def invalidate(self, url: str) -> bool:
        """
        Invalidate a specific cached URL.
        
        Args:
            url: The URL to invalidate
            
        Returns:
            True if the entry was found and removed
        """
        cache_key = self._get_cache_key(url)
        if cache_key in self._cache:
            del self._cache[cache_key]
            return True
        return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "HttpFetcher":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()




