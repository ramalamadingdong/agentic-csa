"""WPILib documentation plugin implementation."""

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
    """A page in the WPILib index."""
    
    url: str
    title: str
    section: str
    language: str
    version: str
    content: str
    content_preview: str


class Plugin(PluginBase):
    """
    WPILib core documentation plugin.
    
    Provides access to the official WPILib documentation at docs.wpilib.org.
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
        return "wpilib"
    
    @property
    def display_name(self) -> str:
        return "WPILib"
    
    @property
    def description(self) -> str:
        return "Official WPILib documentation for FRC robot programming"
    
    @property
    def supported_versions(self) -> list[str]:
        return ["2025", "2024", "2023"]
    
    @property
    def supported_languages(self) -> list[str]:
        return ["Java", "Python", "C++"]
    
    @property
    def base_urls(self) -> list[str]:
        return [
            "https://docs.wpilib.org",
            "https://first.wpi.edu",
            "http://docs.wpilib.org"
        ]
    
    async def initialize(self, config: PluginConfig) -> None:
        """Initialize the plugin by loading index files."""
        self._config = config
        
        # Initialize HTTP fetcher
        self._fetcher = HttpFetcher(cache_ttl_seconds=3600)
        
        # Load index for each configured version
        for version in config.versions:
            await self._load_index(version)
        
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
        logger.info(f"WPILib plugin initialized with {len(self._pages)} pages")
    
    async def _load_index(self, version: str) -> None:
        """Load index file for a specific version."""
        index_file = self.data_dir / f"index_{version}.json"
        
        if not index_file.exists():
            logger.warning(f"Index file not found: {index_file}")
            return
        
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._index_data[version] = data
            
            # Parse pages
            for page_data in data.get("pages", []):
                page = IndexPage(
                    url=page_data["url"],
                    title=page_data["title"],
                    section=page_data.get("section", "General"),
                    language=page_data.get("language", "All"),
                    version=version,
                    content=page_data.get("content", ""),
                    content_preview=page_data.get("content_preview", "")
                )
                self._pages.append(page)
            
            logger.info(f"Loaded {len(data.get('pages', []))} pages from {index_file}")
            
        except Exception as e:
            logger.error(f"Error loading index {index_file}: {e}")
    
    def _build_sections_cache(self) -> None:
        """Build cache of documentation sections."""
        sections: dict[str, dict[str, DocSection]] = {}
        
        for page in self._pages:
            key = f"{page.version}:{page.language}"
            if key not in sections:
                sections[key] = {}
            
            section_name = page.section
            if section_name not in sections[key]:
                sections[key][section_name] = DocSection(
                    name=section_name,
                    vendor=self.name,
                    page_count=0
                )
            
            sections[key][section_name].page_count += 1
        
        # Convert to list format
        for key, section_dict in sections.items():
            self._sections_cache[key] = list(section_dict.values())
    
    async def search(
        self,
        query: str,
        version: Optional[str] = None,
        language: Optional[str] = None,
        max_results: int = 10
    ) -> list[SearchResult]:
        """Search WPILib documentation."""
        if not self._search_index.is_built:
            return []
        
        # Define filter function
        def filter_fn(page: IndexPage) -> bool:
            if version and page.version != version:
                return False
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
                version=page.version,
                content_preview=page.content_preview or page.content[:300],
                score=sr.score
            ))
        
        return results
    
    async def fetch_page(self, url: str) -> Optional[PageContent]:
        """Fetch and clean a WPILib documentation page."""
        if self._fetcher is None:
            return None
        
        try:
            # Fetch HTML
            html = await self._fetcher.fetch(url)
            
            # Extract content
            content = self._html_cleaner.extract_content(html, url)
            title = self._html_cleaner.extract_title(html) or "WPILib Documentation"
            
            # Try to find page in index for metadata
            page_info = self._find_page_by_url(url)
            
            return PageContent(
                url=url,
                title=title,
                content=content,
                vendor=self.display_name,
                language=page_info.language if page_info else None,
                version=page_info.version if page_info else None,
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
        # Use first configured version if not specified
        if version is None:
            version = self._config.versions[0] if self._config else "2025"
        
        if language is None:
            language = "Java"
        
        key = f"{version}:{language}"
        sections = self._sections_cache.get(key, [])
        
        # If no language-specific sections, try "All"
        if not sections:
            key = f"{version}:All"
            sections = self._sections_cache.get(key, [])
        
        return sections
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._fetcher:
            await self._fetcher.close()
            self._fetcher = None
        
        self._pages.clear()
        self._index_data.clear()
        self._sections_cache.clear()
        
        await super().shutdown()




