# FIRST Agentic CSA

A plugin-based FRC documentation agent implemented as a Model Context Protocol (MCP) server. Search across WPILib and vendor documentation (REV, CTRE, Redux, PhotonVision) using natural language queries. Built for FIRST Robotics Competition teams and CSAs (Control System Advisors).

## Features

- **Unified Search**: Query WPILib + vendor docs with a single tool
- **Plugin Architecture**: Extensible system for adding new documentation sources
- **BM25 Ranking**: High-quality text search without embedding costs
- **Multi-Vendor Support**: WPILib, REV Robotics, CTRE Phoenix, Redux Robotics, PhotonVision
- **Language Filtering**: Filter results by Java, Python, or C++
- **Version Support**: Search specific documentation versions (2024, 2025, etc.)

## Installation

### Quick Install (PyPI)

```bash
# Using uvx (recommended)
uvx first-agentic-csa

# Or with pip
pip install first-agentic-csa
```

### From Source

If you want to modify or contribute to the project:

1. **Install uv** (fast Python package manager):

   **Windows (PowerShell):**
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   **macOS/Linux:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and install:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/first-agentic-csa.git
   cd first-agentic-csa
   uv sync
   ```

## Quick Start

### Running the Server

```bash
# With uv
uv run first-agentic-csa

# Or directly
python -m wpilib_mcp.server
```

### Configure in Claude Desktop / Cursor

Add to your MCP configuration (`claude_desktop_config.json` or Cursor settings):

```json
{
  "mcpServers": {
    "frc-docs": {
      "command": "uvx",
      "args": ["first-agentic-csa"]
    }
  }
}
```

If running from source:
```json
{
  "mcpServers": {
    "frc-docs": {
      "command": "uv",
      "args": ["--directory", "/path/to/first-agentic-csa", "run", "first-agentic-csa"]
    }
  }
}
```

### Configure in Other MCP Clients

The server uses stdio transport and is compatible with any MCP client.

## Available Tools

### `search_frc_docs`

Search FRC documentation across WPILib and vendor libraries.

```
query: "SparkMax configure"
vendors: ["all"] | ["wpilib", "rev", "ctre", "redux"]
version: "2025"
language: "Java" | "Python" | "C++"
max_results: 1-25
```

### `fetch_frc_doc_page`

Fetch the full content of a documentation page by URL.

```
url: "https://docs.wpilib.org/en/stable/docs/software/commandbased/commands.html"
```

### `list_frc_doc_sections`

List available documentation sections from vendors.

```
vendors: ["all"] | ["wpilib", "rev"]
version: "2025"
language: "Java"
```

## Configuration

Edit `config.json` to customize plugin settings:

```json
{
  "plugins": {
    "wpilib": {
      "enabled": true,
      "versions": ["2025"],
      "languages": ["Java", "Python", "C++"]
    },
    "rev": {
      "enabled": true,
      "languages": ["Java", "C++"]
    },
    "ctre": {
      "enabled": false
    }
  },
  "cache": {
    "ttl_seconds": 3600
  },
  "search": {
    "default_max_results": 10,
    "default_language": "Java"
  }
}
```

## Supported Plugins

| Plugin | Vendor | Documentation |
|--------|--------|---------------|
| `wpilib` | WPILib | docs.wpilib.org |
| `rev` | REV Robotics | docs.revrobotics.com |
| `ctre` | CTRE Phoenix | v6.docs.ctr-electronics.com |
| `redux` | Redux Robotics | docs.reduxrobotics.com |
| `photonvision` | PhotonVision | docs.photonvision.org |

## Building Documentation Indexes

Each plugin has its own index builder that vendors can maintain independently.

### Using the convenience wrapper:

```bash
# Build all plugin indexes
python scripts/build_index.py all

# Build specific vendor
python scripts/build_index.py wpilib --version 2025
python scripts/build_index.py rev
python scripts/build_index.py ctre
```

### Running plugin builders directly:

```bash
# Each plugin has its own build_index.py with vendor-specific options
python -m wpilib_mcp.plugins.wpilib.build_index --version stable --verbose
python -m wpilib_mcp.plugins.rev.build_index --verbose
python -m wpilib_mcp.plugins.ctre.build_index --version stable
python -m wpilib_mcp.plugins.redux.build_index
```

## Plugin Development

Create a new plugin by following this structure:

```
plugins/
└── myplugin/
    ├── __init__.py
    ├── plugin.py        # Must export `Plugin` class
    ├── build_index.py   # Index builder script (vendor-maintained)
    └── data/
        └── index.json
```

Your `Plugin` class must implement `PluginBase`, and you should provide a `build_index.py` script:

### Plugin Implementation

Your `Plugin` class must implement `PluginBase`:

```python
from wpilib_mcp.plugins.base import PluginBase, PluginConfig, SearchResult, PageContent, DocSection

class Plugin(PluginBase):
    @property
    def name(self) -> str:
        return "myplugin"
    
    @property
    def display_name(self) -> str:
        return "My Plugin"
    
    @property
    def description(self) -> str:
        return "Description of my plugin"
    
    @property
    def supported_versions(self) -> list[str]:
        return ["2025"]
    
    @property
    def supported_languages(self) -> list[str]:
        return ["Java", "Python"]
    
    @property
    def base_urls(self) -> list[str]:
        return ["https://docs.example.com"]
    
    async def initialize(self, config: PluginConfig) -> None:
        # Load index, build search corpus
        pass
    
    async def search(self, query, version=None, language=None, max_results=10) -> list[SearchResult]:
        # Return search results
        pass
    
    async def fetch_page(self, url) -> PageContent:
        # Fetch and clean page content
        pass
    
    async def list_sections(self, version=None, language=None) -> list[DocSection]:
        # Return documentation sections
        pass
```

### Index Builder

Create a `build_index.py` that extends `BaseIndexBuilder`:

```python
from wpilib_mcp.utils.indexer import BaseIndexBuilder

class MyPluginIndexBuilder(BaseIndexBuilder):
    def __init__(self):
        super().__init__(
            vendor="myplugin",
            base_url="https://docs.example.com",
            max_pages=200,
        )
    
    @property
    def start_urls(self) -> list[str]:
        return ["https://docs.example.com/getting-started"]
    
    def should_crawl(self, url: str) -> bool:
        return "docs.example.com" in url
    
    def extract_section(self, soup, url) -> str:
        # Return section name based on URL/content
        return "General"
    
    def extract_language(self, soup, url) -> str:
        return "All"

if __name__ == "__main__":
    import asyncio
    asyncio.run(MyPluginIndexBuilder().build_and_save("latest", Path("data/index.json")))
```

## Index File Format

Each plugin uses a JSON index with this structure:

```json
{
  "vendor": "myplugin",
  "version": "2025",
  "built_at": "2025-01-15T00:00:00Z",
  "pages": [
    {
      "url": "https://docs.example.com/page",
      "title": "Page Title",
      "section": "Section Name",
      "language": "Java",
      "content": "Full searchable content...",
      "content_preview": "First 300 chars for display..."
    }
  ]
}
```

## Development

### Running Tests

```bash
uv run pytest tests/ -v
```

### Project Structure

```
wpilib-mcp/
├── pyproject.toml          # Project configuration
├── config.json             # User configuration
├── src/wpilib_mcp/
│   ├── server.py           # MCP server entry point
│   ├── plugin_loader.py    # Plugin discovery/loading
│   ├── tool_router.py      # Routes tools to plugins
│   ├── utils/
│   │   ├── fetch.py        # HTTP with caching
│   │   ├── html.py         # HTML cleaning
│   │   └── search.py       # BM25 search
│   └── plugins/
│       ├── base.py         # Plugin base class
│       ├── wpilib/         # WPILib plugin
│       ├── rev/            # REV plugin
│       ├── ctre/           # CTRE plugin
│       └── redux/          # Redux plugin
├── scripts/
│   └── build_index.py      # Index builder script
└── tests/
    ├── test_search.py
    └── test_plugins.py
```

## Example Queries

**Finding Command-Based Programming docs:**
```
search_frc_docs(query="command based programming subsystems", vendors=["wpilib"])
```

**Comparing motor controllers:**
```
search_frc_docs(query="SparkMax configuration", vendors=["rev"])
search_frc_docs(query="TalonFX configuration", vendors=["ctre"])
```

**Looking up specific hardware:**
```
search_frc_docs(query="CANcoder absolute position swerve", vendors=["ctre"])
search_frc_docs(query="through bore encoder", vendors=["rev"])
```

**Cross-vendor search:**
```
search_frc_docs(query="brushless motor closed loop velocity control", vendors=["all"])
```

## License

BSD-3-Clause License - see LICENSE file for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Add tests for new functionality
3. Submit a pull request

For new vendor plugins, please include:
- Complete plugin implementation
- Pre-built index file
- Documentation updates