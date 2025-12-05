"""MCP server entry point with unified tool registration."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .plugin_loader import PluginLoader, load_config
from .tool_router import (
    ToolRouter,
    format_search_results,
    format_page_content,
    format_sections
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


# Global state
_server: Optional[Server] = None
_router: Optional[ToolRouter] = None
_config: dict = {}


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("wpilib-mcp")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available MCP tools."""
        return [
            Tool(
                name="search_frc_docs",
                description=(
                    "Search FRC documentation across WPILib and vendor libraries "
                    "(REV, CTRE, Redux, etc.). Returns ranked results with titles, "
                    "URLs, and content previews. Use vendors=['all'] for cross-vendor "
                    "queries, or specify vendors to narrow search."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (e.g., 'SparkMax configure', 'PID tuning')"
                        },
                        "vendors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": ["all"],
                            "description": "Vendors to search: ['all'] or specific like ['wpilib', 'rev', 'ctre']"
                        },
                        "version": {
                            "type": "string",
                            "default": "2025",
                            "description": "Documentation version (e.g., '2025', '2024')"
                        },
                        "language": {
                            "type": "string",
                            "enum": ["Java", "Python", "C++"],
                            "default": "Java",
                            "description": "Programming language filter"
                        },
                        "max_results": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 25,
                            "default": 10,
                            "description": "Maximum results (fewer for quick lookups, more for research)"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="fetch_frc_doc_page",
                description=(
                    "Fetch the full content of an FRC documentation page. "
                    "Automatically routes to the correct plugin based on URL domain. "
                    "Returns cleaned text content suitable for answering questions."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Full URL of the documentation page to fetch"
                        }
                    },
                    "required": ["url"]
                }
            ),
            Tool(
                name="list_frc_doc_sections",
                description=(
                    "List available FRC documentation sections/categories. "
                    "Useful for browsing what documentation is available from each vendor."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "vendors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": ["all"],
                            "description": "Vendors to list: ['all'] or specific like ['wpilib', 'rev']"
                        },
                        "version": {
                            "type": "string",
                            "default": "2025",
                            "description": "Documentation version"
                        },
                        "language": {
                            "type": "string",
                            "enum": ["Java", "Python", "C++"],
                            "default": "Java",
                            "description": "Programming language filter"
                        }
                    }
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls."""
        global _router
        
        if _router is None:
            return [TextContent(
                type="text",
                text="Error: Server not initialized. No plugins loaded."
            )]
        
        try:
            if name == "search_frc_docs":
                return await handle_search(arguments)
            elif name == "fetch_frc_doc_page":
                return await handle_fetch(arguments)
            elif name == "list_frc_doc_sections":
                return await handle_list_sections(arguments)
            else:
                return [TextContent(
                    type="text",
                    text=f"Unknown tool: {name}"
                )]
        except Exception as e:
            logger.error(f"Tool error ({name}): {e}", exc_info=True)
            return [TextContent(
                type="text",
                text=f"Error executing {name}: {str(e)}"
            )]
    
    return server


async def handle_search(arguments: dict) -> list[TextContent]:
    """Handle search_frc_docs tool call."""
    global _router, _config
    
    query = arguments.get("query", "")
    if not query:
        return [TextContent(type="text", text="Error: query is required")]
    
    # Get defaults from config
    search_config = _config.get("search", {})
    
    vendors = arguments.get("vendors", ["all"])
    version = arguments.get("version", search_config.get("default_version", "2025"))
    language = arguments.get("language", search_config.get("default_language", "Java"))
    max_results = arguments.get("max_results", search_config.get("default_max_results", 10))
    
    # Clamp max_results
    max_results = max(1, min(25, max_results))
    
    logger.info(
        f"Search: query={query!r}, vendors={vendors}, "
        f"version={version}, language={language}, max={max_results}"
    )
    
    results = await _router.search(
        query=query,
        vendors=vendors,
        version=version,
        language=language,
        max_results=max_results
    )
    
    formatted = format_search_results(results)
    return [TextContent(type="text", text=formatted)]


async def handle_fetch(arguments: dict) -> list[TextContent]:
    """Handle fetch_frc_doc_page tool call."""
    global _router
    
    url = arguments.get("url", "")
    if not url:
        return [TextContent(type="text", text="Error: url is required")]
    
    logger.info(f"Fetch page: {url}")
    
    page = await _router.fetch_page(url)
    
    if page is None:
        # Provide helpful error with available vendors
        plugin_name = _router.find_plugin_for_url(url)
        if plugin_name:
            return [TextContent(
                type="text",
                text=f"Error: Could not fetch page from {plugin_name} plugin. "
                     f"The page may not exist or be temporarily unavailable."
            )]
        else:
            vendors = ", ".join(_router.available_vendors)
            return [TextContent(
                type="text",
                text=f"Error: No plugin handles this URL. "
                     f"Available vendors: {vendors}"
            )]
    
    formatted = format_page_content(page)
    return [TextContent(type="text", text=formatted)]


async def handle_list_sections(arguments: dict) -> list[TextContent]:
    """Handle list_frc_doc_sections tool call."""
    global _router, _config
    
    search_config = _config.get("search", {})
    
    vendors = arguments.get("vendors", ["all"])
    version = arguments.get("version", search_config.get("default_version", "2025"))
    language = arguments.get("language", search_config.get("default_language", "Java"))
    
    logger.info(f"List sections: vendors={vendors}, version={version}, language={language}")
    
    sections = await _router.list_sections(
        vendors=vendors,
        version=version,
        language=language
    )
    
    formatted = format_sections(sections)
    return [TextContent(type="text", text=formatted)]


async def initialize_server(config_path: Optional[Path] = None) -> None:
    """Initialize the server with plugins."""
    global _router, _config
    
    # Load configuration
    _config = load_config(config_path)
    logger.info("Configuration loaded")
    
    # Load and initialize plugins
    loader = PluginLoader()
    plugins = await loader.load_and_initialize_plugins(_config, fail_fast=False)
    
    if not plugins:
        logger.warning("No plugins were loaded! Server will have limited functionality.")
    else:
        logger.info(f"Loaded {len(plugins)} plugin(s): {list(plugins.keys())}")
    
    # Create router
    _router = ToolRouter(plugins)
    
    # Log plugin info
    for info in _router.get_plugin_info():
        logger.info(
            f"  - {info['display_name']}: "
            f"versions={info['versions']}, languages={info['languages']}"
        )


async def run_server() -> None:
    """Run the MCP server."""
    global _server
    
    # Initialize
    await initialize_server()
    
    # Create server
    _server = create_server()
    
    logger.info("Starting WPILib MCP server...")
    
    # Run with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await _server.run(
            read_stream,
            write_stream,
            _server.create_initialization_options()
        )


def main() -> None:
    """Entry point for the MCP server."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()




