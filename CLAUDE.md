# CLAUDE.md - Project Guide for AI Assistants

## Project Overview

**FIRST Agentic CSA** is an MCP (Model Context Protocol) server that provides intelligent documentation search across FIRST Robotics Competition (FRC) documentation. It aggregates docs from multiple vendors (WPILib, REV Robotics, CTRE Phoenix, Redux, PhotonVision) and enables natural language queries via AI assistants.

## Tech Stack

- **Language:** Python 3.11+
- **Package Manager:** uv (Astral's Rust-based manager)
- **Protocol:** MCP 2025-06-18 schema
- **Search:** BM25 ranking via `rank-bm25`
- **HTTP:** httpx with async support
- **HTML Parsing:** BeautifulSoup4 + lxml
- **Build:** Hatchling
- **Testing:** pytest with asyncio

## Project Structure

```
src/wpilib_mcp/
├── server.py           # MCP server entry point & tool registration
├── tool_router.py      # Routes tool calls to plugins
├── plugin_loader.py    # Plugin discovery & loading
├── plugins/            # Vendor plugin implementations
│   ├── base.py         # PluginBase abstract class
│   ├── wpilib/         # WPILib core docs
│   ├── rev/            # REV Robotics (SparkMax)
│   ├── ctre/           # CTRE Phoenix (TalonFX)
│   ├── redux/          # Redux Robotics
│   └── photonvision/   # PhotonVision
└── utils/
    ├── search.py       # BM25 search indexing
    ├── fetch.py        # HTTP fetching with caching
    ├── html.py         # HTML cleaning & extraction
    └── indexer.py      # Index management

tests/                  # pytest test suite
scripts/                # Utility scripts (index building)
config.json             # Runtime configuration
server.json             # MCP server manifest
```

## Common Commands

```bash
# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Run server locally
uv run first-agentic-csa

# Build package
uv build

# Build documentation indexes
python scripts/build_index.py all
python scripts/build_index.py wpilib --version 2025
python scripts/build_index.py rev
```

## Architecture Patterns

### Plugin System
- Each vendor implements a Plugin class extending `PluginBase`
- Plugins are loaded dynamically based on `config.json`
- Lifecycle: load → initialize → search/fetch → shutdown

### Async Pattern
All I/O operations are async:
```python
async def search(query, version, language, max_results) -> list[SearchResult]
async def fetch_page(url) -> Optional[PageContent]
```

### Key Data Classes
```python
@dataclass
class SearchResult:
    url, title, section, vendor, language, version, content_preview, score

@dataclass
class PageContent:
    url, title, content, vendor, language, version, section, last_fetched
```

### MCP Tools Exposed
1. `search_frc_docs` - Multi-vendor search with filters
2. `fetch_frc_doc_page` - Full page content retrieval
3. `list_frc_doc_sections` - Browse available documentation

## Coding Conventions

- Use async/await for all I/O operations
- Type hints on all function signatures
- Dataclasses for structured data
- Graceful error handling (don't crash the server)
- Pre-built JSON indexes stored in each plugin's `data/` directory

## Configuration

`config.json` controls:
- Plugin enable/disable
- Supported languages per vendor (Java, Python, C++)
- Supported versions (2024, 2025)
- Cache TTL and size limits
- Default search parameters

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_plugins.py -v
uv run pytest tests/test_search.py -v
```

## Entry Point

The package exposes `first-agentic-csa` command which runs `wpilib_mcp.server:main()`
