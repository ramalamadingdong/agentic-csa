"""Routes unified MCP tools to appropriate plugins."""

import logging
from typing import Optional

from .plugins.base import PluginBase, SearchResult, PageContent, DocSection
from .utils.search import ScoredResult, merge_search_results


logger = logging.getLogger(__name__)


class ToolRouter:
    """
    Routes unified tool calls to the appropriate plugins.
    
    Provides the logic behind the 3 unified MCP tools:
    - search_frc_docs: Multi-vendor search with result merging
    - fetch_frc_doc_page: URL-based routing to correct plugin
    - list_frc_doc_sections: Aggregate sections from plugins
    """
    
    def __init__(self, plugins: dict[str, PluginBase]):
        """
        Initialize the router with loaded plugins.
        
        Args:
            plugins: Dictionary of plugin name -> plugin instance
        """
        self._plugins = plugins
    
    def update_plugins(self, plugins: dict[str, PluginBase]) -> None:
        """Update the plugins dictionary."""
        self._plugins = plugins
    
    @property
    def available_vendors(self) -> list[str]:
        """Get list of available vendor names."""
        return list(self._plugins.keys())
    
    def get_plugin_info(self) -> list[dict]:
        """Get information about all loaded plugins."""
        info = []
        for name, plugin in self._plugins.items():
            info.append({
                "name": name,
                "display_name": plugin.display_name,
                "description": plugin.description,
                "versions": plugin.supported_versions,
                "languages": plugin.supported_languages,
                "initialized": plugin.is_initialized
            })
        return info
    
    def _resolve_vendors(self, vendors: list[str]) -> list[str]:
        """
        Resolve vendor list, expanding 'all' to all available vendors.
        
        Args:
            vendors: List of vendor names or ["all"]
            
        Returns:
            List of actual vendor names to query
        """
        if not vendors or vendors == ["all"] or "all" in vendors:
            return list(self._plugins.keys())
        
        # Filter to only valid vendors
        valid = [v for v in vendors if v in self._plugins]
        if len(valid) < len(vendors):
            invalid = set(vendors) - set(valid)
            logger.warning(f"Unknown vendors ignored: {invalid}")
        
        return valid
    
    async def search(
        self,
        query: str,
        vendors: list[str] = None,
        version: Optional[str] = None,
        language: Optional[str] = None,
        max_results: int = 10
    ) -> list[SearchResult]:
        """
        Search across multiple vendors and merge results.
        
        Args:
            query: Search query string
            vendors: List of vendors to search (["all"] for all)
            version: Filter by version
            language: Filter by language (Java/Python/C++)
            max_results: Maximum results to return
            
        Returns:
            Merged and ranked list of SearchResult objects
        """
        if vendors is None:
            vendors = ["all"]
        
        target_vendors = self._resolve_vendors(vendors)
        
        if not target_vendors:
            logger.warning("No valid vendors to search")
            return []
        
        # Collect results from each plugin
        all_results: list[list[ScoredResult[SearchResult]]] = []
        
        for vendor_name in target_vendors:
            plugin = self._plugins.get(vendor_name)
            if plugin is None or not plugin.is_initialized:
                continue
            
            try:
                results = await plugin.search(
                    query=query,
                    version=version,
                    language=language,
                    max_results=max_results
                )
                
                # Wrap in ScoredResult for merging
                scored = [
                    ScoredResult(item=r, score=r.score)
                    for r in results
                ]
                all_results.append(scored)
                
                logger.debug(f"Plugin {vendor_name} returned {len(results)} results")
                
            except Exception as e:
                logger.error(f"Search error in plugin {vendor_name}: {e}")
                # Continue with other plugins
        
        # Merge results from all plugins
        merged = merge_search_results(all_results, max_results)
        
        # Extract the SearchResult objects
        return [sr.item for sr in merged]
    
    async def fetch_page(self, url: str) -> Optional[PageContent]:
        """
        Fetch a documentation page, routing to the correct plugin.
        
        Args:
            url: The page URL to fetch
            
        Returns:
            PageContent if successful, None if no plugin handles the URL
        """
        # Find the plugin that owns this URL
        for name, plugin in self._plugins.items():
            if plugin.owns_url(url):
                logger.debug(f"URL {url} routed to plugin {name}")
                try:
                    return await plugin.fetch_page(url)
                except Exception as e:
                    logger.error(f"Fetch error in plugin {name}: {e}")
                    return None
        
        logger.warning(f"No plugin found for URL: {url}")
        return None
    
    def find_plugin_for_url(self, url: str) -> Optional[str]:
        """
        Find which plugin handles a URL.
        
        Args:
            url: URL to check
            
        Returns:
            Plugin name if found, None otherwise
        """
        for name, plugin in self._plugins.items():
            if plugin.owns_url(url):
                return name
        return None
    
    async def list_sections(
        self,
        vendors: list[str] = None,
        version: Optional[str] = None,
        language: Optional[str] = None
    ) -> dict[str, list[DocSection]]:
        """
        List documentation sections from requested vendors.
        
        Args:
            vendors: List of vendors (["all"] for all)
            version: Filter by version
            language: Filter by language
            
        Returns:
            Dictionary of vendor name -> list of DocSection objects
        """
        if vendors is None:
            vendors = ["all"]
        
        target_vendors = self._resolve_vendors(vendors)
        result: dict[str, list[DocSection]] = {}
        
        for vendor_name in target_vendors:
            plugin = self._plugins.get(vendor_name)
            if plugin is None or not plugin.is_initialized:
                continue
            
            try:
                sections = await plugin.list_sections(
                    version=version,
                    language=language
                )
                result[vendor_name] = sections
                
            except Exception as e:
                logger.error(f"List sections error in plugin {vendor_name}: {e}")
                result[vendor_name] = []
        
        return result


def format_search_results(results: list[SearchResult]) -> str:
    """
    Format search results for MCP tool response.
    
    Args:
        results: List of SearchResult objects
        
    Returns:
        Formatted string suitable for LLM consumption
    """
    if not results:
        return "No results found."
    
    lines = [f"Found {len(results)} result(s):\n"]
    
    for i, result in enumerate(results, 1):
        lines.append(f"## {i}. {result.title}")
        lines.append(f"**Vendor:** {result.vendor} | **Section:** {result.section}")
        if result.language:
            lines.append(f"**Language:** {result.language}")
        lines.append(f"**URL:** {result.url}")
        lines.append(f"\n{result.content_preview}\n")
        lines.append("---\n")
    
    return "\n".join(lines)


def format_page_content(page: PageContent) -> str:
    """
    Format page content for MCP tool response.
    
    Args:
        page: PageContent object
        
    Returns:
        Formatted string suitable for LLM consumption
    """
    lines = [
        f"# {page.title}",
        f"**Source:** {page.vendor}",
        f"**URL:** {page.url}",
    ]
    
    if page.language:
        lines.append(f"**Language:** {page.language}")
    if page.version:
        lines.append(f"**Version:** {page.version}")
    if page.section:
        lines.append(f"**Section:** {page.section}")
    
    lines.append("\n---\n")
    lines.append(page.content)
    
    return "\n".join(lines)


def format_sections(sections_by_vendor: dict[str, list[DocSection]]) -> str:
    """
    Format documentation sections for MCP tool response.
    
    Args:
        sections_by_vendor: Dictionary of vendor -> sections
        
    Returns:
        Formatted string suitable for LLM consumption
    """
    if not sections_by_vendor:
        return "No documentation sections available."
    
    lines = ["# Available Documentation Sections\n"]
    
    for vendor, sections in sections_by_vendor.items():
        lines.append(f"## {vendor.upper()}\n")
        
        if not sections:
            lines.append("No sections available.\n")
            continue
        
        for section in sections:
            lines.append(f"### {section.name}")
            if section.description:
                lines.append(f"{section.description}")
            if section.page_count > 0:
                lines.append(f"*{section.page_count} pages*")
            if section.url:
                lines.append(f"URL: {section.url}")
            
            if section.subsections:
                for sub in section.subsections:
                    lines.append(f"  - {sub.name}")
            
            lines.append("")
    
    return "\n".join(lines)




