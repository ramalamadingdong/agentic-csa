"""REV Robotics documentation plugin implementation."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..base import (
    PluginBase,
    PluginConfig,
    SearchResult,
    PageContent,
    DocSection
)
from ...utils.fetch import HttpFetcher
from ...utils.html import HtmlCleaner
from ...utils.search import BM25SearchIndex


logger = logging.getLogger(__name__)


@dataclass
class IndexPage:
    """A page in the REV index."""
    
    url: str
    title: str
    section: str
    language: str
    content: str
    content_preview: str


class Plugin(PluginBase):
    """
    REV Robotics documentation plugin.
    
    Provides access to REV documentation for SparkMax, SparkFlex,
    and other REV hardware and software.
    """
    
    def __init__(self):
        super().__init__()
        self._index_data: dict = {}
        self._pages: list[IndexPage] = []
        self._search_index: BM25SearchIndex[IndexPage] = BM25SearchIndex()
        self._fetcher: Optional[HttpFetcher] = None
        self._html_cleaner = HtmlCleaner()
        self._sections_cache: dict[str, list[DocSection]] = {}
    
    @property
    def name(self) -> str:
        return "rev"
    
    @property
    def display_name(self) -> str:
        return "REV Robotics"
    
    @property
    def description(self) -> str:
        return "REV Robotics documentation for SparkMax, SparkFlex, and related hardware"
    
    @property
    def supported_versions(self) -> list[str]:
        return ["2025", "2024"]
    
    @property
    def supported_languages(self) -> list[str]:
        return ["Java", "C++"]
    
    @property
    def base_urls(self) -> list[str]:
        return [
            "https://docs.revrobotics.com",
            "https://revrobotics.com/docs",
            "http://docs.revrobotics.com"
        ]
    
    async def initialize(self, config: PluginConfig) -> None:
        """Initialize the plugin by loading index files."""
        self._config = config
        
        # Initialize HTTP fetcher
        self._fetcher = HttpFetcher(cache_ttl_seconds=3600)
        
        # Load index
        await self._load_index()
        
        # Build BM25 search index
        if self._pages:
            self._search_index.build(
                items=self._pages,
                text_extractor=lambda p: f"{p.title} {p.section} {p.content}"
            )
            logger.info(f"Built search index with {self._search_index.size} pages")
        
        # Build sections cache
        self._build_sections_cache()
        
        self._initialized = True
        logger.info(f"REV plugin initialized with {len(self._pages)} pages")
    
    async def _load_index(self) -> None:
        """Load index file."""
        index_file = self.data_dir / "index.json"
        
        if not index_file.exists():
            logger.warning(f"Index file not found: {index_file}")
            return
        
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._index_data = data
            
            # Parse pages
            for page_data in data.get("pages", []):
                page = IndexPage(
                    url=page_data["url"],
                    title=page_data["title"],
                    section=page_data.get("section", "General"),
                    language=page_data.get("language", "All"),
                    content=page_data.get("content", ""),
                    content_preview=page_data.get("content_preview", "")
                )
                self._pages.append(page)
            
            logger.info(f"Loaded {len(data.get('pages', []))} pages from {index_file}")
            
        except Exception as e:
            logger.error(f"Error loading index {index_file}: {e}")
    
    def _build_sections_cache(self) -> None:
        """Build cache of documentation sections."""
        sections: dict[str, DocSection] = {}
        
        for page in self._pages:
            section_name = page.section
            if section_name not in sections:
                sections[section_name] = DocSection(
                    name=section_name,
                    vendor=self.name,
                    page_count=0
                )
            
            sections[section_name].page_count += 1
        
        self._sections_cache["default"] = list(sections.values())
    
    async def search(
        self,
        query: str,
        version: Optional[str] = None,
        language: Optional[str] = None,
        max_results: int = 10
    ) -> list[SearchResult]:
        """Search REV documentation."""
        if not self._search_index.is_built:
            return []
        
        # Define filter function
        def filter_fn(page: IndexPage) -> bool:
            if language and page.language not in (language, "All"):
                return False
            return True
        
        # Search with filter
        scored_results = self._search_index.search_with_filter(
            query=query,
            filter_fn=filter_fn,
            max_results=max_results
        )
        
        # Convert to SearchResult objects
        results = []
        for sr in scored_results:
            page = sr.item
            results.append(SearchResult(
                url=page.url,
                title=page.title,
                section=page.section,
                vendor=self.display_name,
                language=page.language,
                version=version or "latest",
                content_preview=page.content_preview or page.content[:300],
                score=sr.score
            ))
        
        return results
    
    async def fetch_page(self, url: str) -> Optional[PageContent]:
        """Fetch and clean a REV documentation page."""
        if self._fetcher is None:
            return None
        
        try:
            # Fetch HTML
            html = await self._fetcher.fetch(url)
            
            # Extract content
            content = self._html_cleaner.extract_content(html, url)
            title = self._html_cleaner.extract_title(html) or "REV Robotics Documentation"
            
            # Try to find page in index for metadata
            page_info = self._find_page_by_url(url)
            
            return PageContent(
                url=url,
                title=title,
                content=content,
                vendor=self.display_name,
                language=page_info.language if page_info else None,
                section=page_info.section if page_info else None,
                last_fetched=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error fetching page {url}: {e}")
            return None
    
    def _find_page_by_url(self, url: str) -> Optional[IndexPage]:
        """Find a page in the index by URL."""
        url_lower = url.lower()
        for page in self._pages:
            if page.url.lower() == url_lower:
                return page
        return None
    
    async def list_sections(
        self,
        version: Optional[str] = None,
        language: Optional[str] = None
    ) -> list[DocSection]:
        """List available documentation sections."""
        return self._sections_cache.get("default", [])
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._fetcher:
            await self._fetcher.close()
            self._fetcher = None
        
        self._pages.clear()
        self._index_data.clear()
        self._sections_cache.clear()
        
        await super().shutdown()




