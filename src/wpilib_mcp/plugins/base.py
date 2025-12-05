"""Base class for documentation plugins."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class SearchResult:
    """A single search result from a plugin."""
    
    url: str
    title: str
    section: str
    vendor: str
    language: str
    version: str
    content_preview: str
    score: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "title": self.title,
            "section": self.section,
            "vendor": self.vendor,
            "language": self.language,
            "version": self.version,
            "content_preview": self.content_preview,
            "score": self.score
        }


@dataclass
class PageContent:
    """Full content of a documentation page."""
    
    url: str
    title: str
    content: str
    vendor: str
    language: Optional[str] = None
    version: Optional[str] = None
    section: Optional[str] = None
    last_fetched: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "vendor": self.vendor,
            "language": self.language,
            "version": self.version,
            "section": self.section,
            "last_fetched": self.last_fetched
        }


@dataclass
class DocSection:
    """A documentation section/category."""
    
    name: str
    vendor: str
    url: Optional[str] = None
    description: Optional[str] = None
    page_count: int = 0
    subsections: list["DocSection"] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "vendor": self.vendor,
            "url": self.url,
            "description": self.description,
            "page_count": self.page_count,
            "subsections": [s.to_dict() for s in self.subsections]
        }


@dataclass
class PluginConfig:
    """Configuration for a plugin."""
    
    enabled: bool = True
    versions: list[str] = field(default_factory=lambda: ["2025"])
    languages: list[str] = field(default_factory=lambda: ["Java", "Python", "C++"])
    custom: dict[str, Any] = field(default_factory=dict)


class PluginBase(ABC):
    """
    Abstract base class for documentation plugins.
    
    Each plugin provides access to a vendor's documentation:
    - WPILib core documentation
    - REV Robotics (SparkMax, SparkFlex)
    - CTRE Phoenix (TalonFX, Falcon)
    - Redux Robotics
    - Playing With Fusion
    - etc.
    """
    
    def __init__(self):
        """Initialize the plugin."""
        self._initialized = False
        self._config: Optional[PluginConfig] = None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for the plugin.
        
        Examples: "wpilib", "rev", "ctre", "redux"
        """
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Human-readable name for the plugin.
        
        Examples: "WPILib", "REV Robotics", "CTRE Phoenix"
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of what this plugin provides."""
        pass
    
    @property
    @abstractmethod
    def supported_versions(self) -> list[str]:
        """List of documentation versions this plugin supports."""
        pass
    
    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """List of programming languages this plugin supports."""
        pass
    
    @property
    @abstractmethod
    def base_urls(self) -> list[str]:
        """
        Base URLs this plugin handles.
        
        Used by owns_url() to route requests.
        """
        pass
    
    @property
    def data_dir(self) -> Path:
        """Get the data directory for this plugin."""
        return Path(__file__).parent / self.name / "data"
    
    @property
    def is_initialized(self) -> bool:
        """Check if the plugin has been initialized."""
        return self._initialized
    
    @abstractmethod
    async def initialize(self, config: PluginConfig) -> None:
        """
        Initialize the plugin with configuration.
        
        This should:
        - Load index files
        - Build BM25 corpus
        - Perform any other setup
        
        Args:
            config: Plugin configuration
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query: str,
        version: Optional[str] = None,
        language: Optional[str] = None,
        max_results: int = 10
    ) -> list[SearchResult]:
        """
        Search this plugin's documentation.
        
        Args:
            query: Search query string
            version: Filter by version (None = all versions)
            language: Filter by language (None = all languages)
            max_results: Maximum results to return
            
        Returns:
            List of search results, sorted by relevance
        """
        pass
    
    @abstractmethod
    async def fetch_page(self, url: str) -> Optional[PageContent]:
        """
        Fetch the full content of a documentation page.
        
        Args:
            url: The page URL to fetch
            
        Returns:
            PageContent if successful, None if page not found/accessible
        """
        pass
    
    @abstractmethod
    async def list_sections(
        self,
        version: Optional[str] = None,
        language: Optional[str] = None
    ) -> list[DocSection]:
        """
        List available documentation sections.
        
        Args:
            version: Filter by version (None = default version)
            language: Filter by language (None = all languages)
            
        Returns:
            List of documentation sections
        """
        pass
    
    def owns_url(self, url: str) -> bool:
        """
        Check if this plugin handles the given URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if this plugin should handle the URL
        """
        url_lower = url.lower()
        for base_url in self.base_urls:
            if url_lower.startswith(base_url.lower()):
                return True
        return False
    
    async def shutdown(self) -> None:
        """
        Clean up plugin resources.
        
        Override if the plugin needs cleanup (close connections, etc.)
        """
        self._initialized = False
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r}, initialized={self._initialized})>"




