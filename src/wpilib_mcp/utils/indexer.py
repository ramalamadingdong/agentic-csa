"""Shared utilities for building documentation indexes."""

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


@dataclass
class PageData:
    """Data for a single documentation page."""
    url: str
    title: str
    section: str
    language: str
    content: str
    content_preview: str


class BaseIndexBuilder(ABC):
    """
    Base class for documentation index builders.
    
    Vendors should subclass this and implement the abstract methods
    to customize crawling and extraction for their documentation site.
    """
    
    def __init__(
        self,
        vendor: str,
        base_url: str,
        max_pages: int = 500,
        max_depth: int = 3,
        rate_limit: float = 0.1
    ):
        """
        Initialize the index builder.
        
        Args:
            vendor: Vendor identifier (e.g., "wpilib", "rev")
            base_url: Base URL for the documentation site
            max_pages: Maximum number of pages to index
            max_depth: Maximum crawl depth from start URLs
            rate_limit: Seconds to wait between requests
        """
        self.vendor = vendor
        self.base_url = base_url
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.rate_limit = rate_limit
        
        self.visited: set[str] = set()
        self.pages: list[PageData] = []
        self.client: Optional[httpx.AsyncClient] = None
    
    @property
    @abstractmethod
    def start_urls(self) -> list[str]:
        """URLs to start crawling from."""
        pass
    
    @abstractmethod
    def should_crawl(self, url: str) -> bool:
        """
        Determine if a URL should be crawled.
        
        Args:
            url: The URL to check
            
        Returns:
            True if the URL should be crawled
        """
        pass
    
    @abstractmethod
    def extract_section(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extract the documentation section from a page.
        
        Args:
            soup: Parsed HTML
            url: Page URL
            
        Returns:
            Section name (e.g., "Command-Based Programming")
        """
        pass
    
    @abstractmethod
    def extract_language(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extract the programming language from a page.
        
        Args:
            soup: Parsed HTML
            url: Page URL
            
        Returns:
            Language name ("Java", "Python", "C++", or "All")
        """
        pass
    
    def extract_title(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """
        Extract page title. Override for custom logic.
        
        Args:
            soup: Parsed HTML
            url: Page URL
            
        Returns:
            Page title or None
        """
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # Clean common suffixes
            title = re.sub(r"\s*[—\-|·].*$", "", title).strip()
            return title
        
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        
        return None
    
    def extract_content(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extract main content from page. Override for custom logic.
        
        Args:
            soup: Parsed HTML
            url: Page URL
            
        Returns:
            Cleaned text content
        """
        # Remove unwanted elements
        for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        
        # Find main content area
        main = (
            soup.find("main") or 
            soup.find("article") or 
            soup.find(class_="content") or
            soup.find(class_="main-content") or
            soup.find(id="content") or
            soup.body
        )
        
        if main is None:
            return ""
        
        # Get text
        text = main.get_text(separator=" ", strip=True)
        
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    
    def extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """
        Extract links from page. Override for custom logic.
        
        Args:
            soup: Parsed HTML
            base_url: Current page URL for resolving relative links
            
        Returns:
            List of absolute URLs
        """
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            
            # Skip anchors, mailto, javascript
            if href.startswith(("#", "mailto:", "javascript:")):
                continue
            
            # Make absolute
            full_url = urljoin(base_url, href)
            
            # Remove fragment
            full_url = full_url.split("#")[0]
            
            # Check if same domain
            if urlparse(full_url).netloc == urlparse(self.base_url).netloc:
                links.append(full_url)
        
        return list(set(links))
    
    def create_preview(self, content: str, max_length: int = 300) -> str:
        """Create a preview snippet from content."""
        if len(content) <= max_length:
            return content
        
        preview = content[:max_length]
        
        # Try to end at sentence
        last_period = preview.rfind(". ")
        if last_period > max_length * 0.5:
            return preview[:last_period + 1]
        
        # End at word boundary
        last_space = preview.rfind(" ")
        if last_space > max_length * 0.7:
            return preview[:last_space] + "..."
        
        return preview + "..."
    
    async def build(self, version: str = "latest") -> dict:
        """
        Build the documentation index.
        
        Args:
            version: Version string for the index
            
        Returns:
            Index dictionary ready for JSON serialization
        """
        logger.info(f"Building index for {self.vendor}...")
        
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": f"WPILib-MCP-{self.vendor}-Indexer/1.0"}
        ) as self.client:
            for start_url in self.start_urls:
                await self._crawl(start_url, depth=0)
                
                if len(self.pages) >= self.max_pages:
                    logger.info(f"Reached max pages limit ({self.max_pages})")
                    break
        
        logger.info(f"Indexed {len(self.pages)} pages for {self.vendor}")
        
        return {
            "vendor": self.vendor,
            "version": version,
            "built_at": datetime.now().isoformat(),
            "pages": [asdict(p) for p in self.pages]
        }
    
    async def _crawl(self, url: str, depth: int) -> None:
        """Recursively crawl URLs."""
        if depth > self.max_depth:
            return
        
        if url in self.visited:
            return
        
        if len(self.pages) >= self.max_pages:
            return
        
        if not self.should_crawl(url):
            return
        
        self.visited.add(url)
        
        try:
            logger.debug(f"Fetching: {url}")
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Extract page data
            page = self._extract_page(soup, url)
            if page and len(page.content) > 100:
                self.pages.append(page)
                logger.info(f"Indexed: {page.title}")
            
            # Find and crawl links
            links = self.extract_links(soup, url)
            for link in links:
                await self._crawl(link, depth + 1)
                await asyncio.sleep(self.rate_limit)
                
        except Exception as e:
            logger.warning(f"Error crawling {url}: {e}")
    
    def _extract_page(self, soup: BeautifulSoup, url: str) -> Optional[PageData]:
        """Extract all page data."""
        title = self.extract_title(soup, url)
        if not title:
            return None
        
        content = self.extract_content(soup, url)
        if not content:
            return None
        
        section = self.extract_section(soup, url)
        language = self.extract_language(soup, url)
        preview = self.create_preview(content)
        
        return PageData(
            url=url,
            title=title,
            section=section,
            language=language,
            content=content,
            content_preview=preview
        )
    
    def save_index(self, index: dict, output_path: Path) -> None:
        """Save index to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved index to {output_path}")
    
    async def build_and_save(self, version: str, output_path: Path) -> None:
        """Build index and save to file."""
        index = await self.build(version)
        self.save_index(index, output_path)




