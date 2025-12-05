"""Tests for plugin system."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from wpilib_mcp.plugins.base import (
    PluginBase,
    PluginConfig,
    SearchResult,
    PageContent,
    DocSection
)
from wpilib_mcp.plugin_loader import PluginLoader, load_config, get_default_config


class MockPlugin(PluginBase):
    """Mock plugin for testing."""
    
    @property
    def name(self) -> str:
        return "mock"
    
    @property
    def display_name(self) -> str:
        return "Mock Plugin"
    
    @property
    def description(self) -> str:
        return "A mock plugin for testing"
    
    @property
    def supported_versions(self) -> list[str]:
        return ["2025"]
    
    @property
    def supported_languages(self) -> list[str]:
        return ["Java", "Python"]
    
    @property
    def base_urls(self) -> list[str]:
        return ["https://mock.example.com"]
    
    async def initialize(self, config: PluginConfig) -> None:
        self._config = config
        self._initialized = True
    
    async def search(self, query, version=None, language=None, max_results=10):
        return [
            SearchResult(
                url="https://mock.example.com/page",
                title="Mock Result",
                section="Testing",
                vendor="Mock Plugin",
                language="Java",
                version="2025",
                content_preview="This is a mock search result.",
                score=1.0
            )
        ]
    
    async def fetch_page(self, url):
        return PageContent(
            url=url,
            title="Mock Page",
            content="This is mock page content.",
            vendor="Mock Plugin"
        )
    
    async def list_sections(self, version=None, language=None):
        return [
            DocSection(name="Testing", vendor="mock", page_count=1)
        ]


class TestPluginBase:
    """Test cases for PluginBase."""
    
    def test_owns_url(self):
        """Test URL ownership detection."""
        plugin = MockPlugin()
        
        assert plugin.owns_url("https://mock.example.com/page")
        assert plugin.owns_url("https://MOCK.EXAMPLE.COM/page")
        assert not plugin.owns_url("https://other.example.com/page")
    
    def test_not_initialized_by_default(self):
        """Test plugin starts uninitialized."""
        plugin = MockPlugin()
        assert not plugin.is_initialized
    
    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test plugin initialization."""
        plugin = MockPlugin()
        config = PluginConfig(
            enabled=True,
            versions=["2025"],
            languages=["Java"]
        )
        
        await plugin.initialize(config)
        
        assert plugin.is_initialized
        assert plugin._config == config
    
    def test_repr(self):
        """Test string representation."""
        plugin = MockPlugin()
        repr_str = repr(plugin)
        
        assert "MockPlugin" in repr_str
        assert "mock" in repr_str


class TestSearchResult:
    """Test cases for SearchResult."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = SearchResult(
            url="https://example.com",
            title="Test",
            section="Section",
            vendor="Vendor",
            language="Java",
            version="2025",
            content_preview="Preview text",
            score=0.95
        )
        
        d = result.to_dict()
        
        assert d["url"] == "https://example.com"
        assert d["title"] == "Test"
        assert d["score"] == 0.95


class TestPluginConfig:
    """Test cases for PluginConfig."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = PluginConfig()
        
        assert config.enabled is True
        assert "2025" in config.versions
        assert "Java" in config.languages
        assert config.custom == {}
    
    def test_custom_values(self):
        """Test custom configuration."""
        config = PluginConfig(
            enabled=False,
            versions=["2024"],
            languages=["Python"],
            custom={"key": "value"}
        )
        
        assert config.enabled is False
        assert config.versions == ["2024"]
        assert config.custom["key"] == "value"


class TestPluginLoader:
    """Test cases for PluginLoader."""
    
    def test_discover_plugins(self):
        """Test plugin discovery."""
        loader = PluginLoader()
        plugins = loader.discover_plugins()
        
        # Should find at least the built-in plugins
        assert isinstance(plugins, list)
    
    def test_get_nonexistent_plugin(self):
        """Test getting a plugin that doesn't exist."""
        loader = PluginLoader()
        plugin = loader.get_plugin("nonexistent")
        
        assert plugin is None
    
    def test_get_all_plugins_empty(self):
        """Test getting all plugins when none loaded."""
        loader = PluginLoader()
        plugins = loader.get_all_plugins()
        
        assert plugins == {}


class TestConfig:
    """Test cases for configuration loading."""
    
    def test_default_config(self):
        """Test default configuration structure."""
        config = get_default_config()
        
        assert "plugins" in config
        assert "wpilib" in config["plugins"]
        assert config["plugins"]["wpilib"]["enabled"] is True
        assert "cache" in config
        assert "search" in config
    
    def test_load_missing_config(self):
        """Test loading missing config file returns defaults."""
        config = load_config(Path("/nonexistent/config.json"))
        
        assert config == get_default_config()


class TestDocSection:
    """Test cases for DocSection."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        section = DocSection(
            name="Command-Based",
            vendor="wpilib",
            url="https://docs.wpilib.org",
            description="Command-based programming",
            page_count=10,
            subsections=[
                DocSection(name="Commands", vendor="wpilib", page_count=3)
            ]
        )
        
        d = section.to_dict()
        
        assert d["name"] == "Command-Based"
        assert d["vendor"] == "wpilib"
        assert d["page_count"] == 10
        assert len(d["subsections"]) == 1
        assert d["subsections"][0]["name"] == "Commands"


class TestPageContent:
    """Test cases for PageContent."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        page = PageContent(
            url="https://example.com/page",
            title="Example Page",
            content="Full page content here.",
            vendor="Example",
            language="Java",
            version="2025",
            section="Examples"
        )
        
        d = page.to_dict()
        
        assert d["url"] == "https://example.com/page"
        assert d["title"] == "Example Page"
        assert d["vendor"] == "Example"
        assert d["language"] == "Java"

