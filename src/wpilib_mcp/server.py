"""MCP server entry point with unified tool registration."""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Fix Windows line endings for MCP protocol compatibility
# Windows uses CRLF (\r\n) but MCP expects LF (\n) only
# Some clients (like Antigravity) are strict about this
if sys.platform == "win32":
    import msvcrt
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)

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
from .utils.context import get_project_context, ProjectContext


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
                    "URLs, and content previews. Use auto_detect=true to automatically "
                    "filter by the project's detected language and vendors."
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
                            "description": "Vendors to search: ['all'] or specific like ['wpilib', 'rev', 'ctre']. Ignored if auto_detect=true."
                        },
                        "version": {
                            "type": "string",
                            "default": "2025",
                            "description": "Documentation version (e.g., '2025', '2024')"
                        },
                        "language": {
                            "type": "string",
                            "enum": ["Java", "Python", "C++"],
                            "description": "Programming language filter. Auto-detected if auto_detect=true."
                        },
                        "max_results": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 25,
                            "default": 10,
                            "description": "Maximum results (fewer for quick lookups, more for research)"
                        },
                        "auto_detect": {
                            "type": "boolean",
                            "default": True,
                            "description": "Auto-detect language and vendors from project files. Recommended for better results."
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="detect_project_context",
                description=(
                    "Detect the FRC project's programming language and vendor libraries "
                    "by scanning source files, build configs, and vendordeps. "
                    "Useful for understanding what hardware/libraries the project uses."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {
                            "type": "string",
                            "description": "Path to project root. Defaults to current working directory."
                        }
                    }
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
            elif name == "detect_project_context":
                return await handle_detect_context(arguments)
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

    # Check if auto_detect is enabled (default: True)
    auto_detect = arguments.get("auto_detect", True)

    # Start with provided or default values
    vendors = arguments.get("vendors", ["all"])
    version = arguments.get("version", search_config.get("default_version", "2025"))
    language = arguments.get("language")  # None if not provided
    max_results = arguments.get("max_results", search_config.get("default_max_results", 10))

    # Auto-detect context if enabled
    context_info = ""
    if auto_detect:
        try:
            context = get_project_context()
            if context.has_context:
                # Use detected language if not explicitly provided
                if language is None and context.language:
                    language = context.language
                    context_info += f"[Auto-detected language: {language}] "

                # Use detected vendors if vendors is "all"
                if (vendors == ["all"] or "all" in vendors) and context.vendors:
                    # Always include wpilib plus detected vendors
                    vendors = list(set(["wpilib"] + context.vendors))
                    context_info += f"[Auto-detected vendors: {', '.join(context.vendors)}] "

                logger.info(f"Context detection: {context.to_dict()}")
        except Exception as e:
            logger.warning(f"Context detection failed: {e}")

    # Fall back to config defaults if still not set
    if language is None:
        language = search_config.get("default_language", "Java")

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

    # Prepend context info if we auto-detected
    formatted = format_search_results(results)
    if context_info:
        formatted = f"{context_info}\n\n{formatted}"

    return [TextContent(type="text", text=formatted)]


async def handle_detect_context(arguments: dict) -> list[TextContent]:
    """Handle detect_project_context tool call."""
    from pathlib import Path

    project_path = arguments.get("project_path")
    path = Path(project_path) if project_path else None

    try:
        context = get_project_context(path)

        lines = ["# Project Context Detection\n"]

        if not context.has_context:
            lines.append("**No FRC project context detected.**\n")
            lines.append("This might mean:")
            lines.append("- Not running from an FRC project directory")
            lines.append("- Project doesn't have standard FRC structure")
            lines.append("- Missing vendordeps or source files\n")
        else:
            if context.language:
                lines.append(f"**Language:** {context.language}")

            if context.vendors:
                lines.append(f"**Vendors:** {', '.join(context.vendors)}")

            lines.append(f"**Confidence:** {context.confidence:.0%}")

            if context.detection_sources:
                lines.append("\n**Detection sources:**")
                for source in context.detection_sources[:10]:
                    lines.append(f"  - {source}")

        lines.append("\n---")
        lines.append("*Use this information to filter search results appropriately.*")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Context detection error: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error detecting project context: {str(e)}"
        )]


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




