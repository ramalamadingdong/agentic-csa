"""AdvantageKit documentation plugin."""

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
from ...utils.markdown import extract_md_title
from ...utils.search import BM25SearchIndex


logger = logging.getLogger(__name__)


@dataclass
class IndexPage:
    url: str
    title: str
    section: str
    language: str
    content: str
    content_preview: str


class Plugin(PluginBase):
    """AdvantageKit documentation plugin for FRC log replay and data logging."""

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
        return "advantagekit"

    @property
    def display_name(self) -> str:
        return "AdvantageKit"

    @property
    def description(self) -> str:
        return "AdvantageKit documentation for FRC data logging and log replay"

    @property
    def supported_versions(self) -> list[str]:
        return ["latest"]

    @property
    def supported_languages(self) -> list[str]:
        return ["Java"]

    @property
    def base_urls(self) -> list[str]:
        return [
            "https://docs.advantagekit.org",
        ]

    async def initialize(self, config: PluginConfig) -> None:
        self._config = config
        self._fetcher = HttpFetcher(cache_ttl_seconds=3600)
        await self._load_index()
        if self._pages:
            self._search_index.build(
                items=self._pages,
                text_extractor=lambda p: f"{p.title} {p.section} {p.content}"
            )
            logger.info(f"Built search index with {self._search_index.size} pages")
        self._build_sections_cache()
        self._initialized = True
        logger.info(f"AdvantageKit plugin initialized with {len(self._pages)} pages")

    async def _load_index(self) -> None:
        index_file = self.data_dir / "index.json"
        if not index_file.exists():
            logger.warning(f"Index file not found: {index_file}")
            return
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._index_data = data
            for page_data in data.get("pages", []):
                page = IndexPage(
                    url=page_data["url"],
                    title=page_data["title"],
                    section=page_data.get("section", "General"),
                    language=page_data.get("language", "Java"),
                    content=page_data.get("content", ""),
                    content_preview=page_data.get("content_preview", "")
                )
                self._pages.append(page)
            logger.info(f"Loaded {len(self._pages)} pages from {index_file}")
        except Exception as e:
            logger.error(f"Error loading index {index_file}: {e}")

    def _build_sections_cache(self) -> None:
        sections: dict[str, DocSection] = {}
        for page in self._pages:
            name = page.section
            if name not in sections:
                sections[name] = DocSection(name=name, vendor=self.name, page_count=0)
            sections[name].page_count += 1
        self._sections_cache["default"] = list(sections.values())

    async def search(
        self,
        query: str,
        version: Optional[str] = None,
        language: Optional[str] = None,
        max_results: int = 10
    ) -> list[SearchResult]:
        if not self._search_index.is_built:
            return []

        def filter_fn(page: IndexPage) -> bool:
            if language and page.language not in (language, "All"):
                return False
            return True

        scored_results = self._search_index.search_with_filter(
            query=query,
            filter_fn=filter_fn,
            max_results=max_results
        )
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
        if self._fetcher is None:
            return None
        page_info = self._find_page_by_url(url)

        # Try GitHub raw markdown source first
        gh_url = _to_github_raw_url(url)
        if gh_url:
            try:
                markdown = await self._fetcher.fetch(gh_url)
                if markdown and len(markdown.strip()) >= 100:
                    title = extract_md_title(markdown) or "AdvantageKit Documentation"
                    return PageContent(
                        url=url,
                        title=title,
                        content=markdown,
                        vendor=self.display_name,
                        language="Java",
                        section=page_info.section if page_info else None,
                        last_fetched=datetime.now().isoformat()
                    )
            except Exception:
                pass

        # Fall back to HTML
        try:
            html = await self._fetcher.fetch(url)
            content = self._html_cleaner.extract_content(html, url)
            title = self._html_cleaner.extract_title(html) or "AdvantageKit Documentation"
            return PageContent(
                url=url,
                title=title,
                content=content,
                vendor=self.display_name,
                language="Java",
                section=page_info.section if page_info else None,
                last_fetched=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Error fetching page {url}: {e}")
            return None

    def _find_page_by_url(self, url: str) -> Optional[IndexPage]:
        url_lower = url.lower().rstrip("/")
        for page in self._pages:
            if page.url.lower().rstrip("/") == url_lower:
                return page
        return None

    async def list_sections(
        self,
        version: Optional[str] = None,
        language: Optional[str] = None
    ) -> list[DocSection]:
        return self._sections_cache.get("default", [])

    async def shutdown(self) -> None:
        if self._fetcher:
            await self._fetcher.close()
            self._fetcher = None
        self._pages.clear()
        self._index_data.clear()
        self._sections_cache.clear()
        await super().shutdown()


GITHUB_RAW = "https://raw.githubusercontent.com/Mechanical-Advantage/AdvantageKit/main/docs/docs"


def _to_github_raw_url(doc_url: str) -> Optional[str]:
    """Convert docs.advantagekit.org URL to GitHub raw markdown URL."""
    prefix = "https://docs.advantagekit.org"
    if not doc_url.startswith(prefix):
        return None
    path = doc_url[len(prefix):].strip("/")
    if not path:
        return f"{GITHUB_RAW}/intro.md"
    # Trailing-slash paths are likely index pages
    if doc_url.endswith("/"):
        return f"{GITHUB_RAW}/{path}/index.md"
    return f"{GITHUB_RAW}/{path}.md"
