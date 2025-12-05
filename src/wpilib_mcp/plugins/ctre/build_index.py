#!/usr/bin/env python3
"""
Build documentation index for CTRE Phoenix.

This script crawls v6.docs.ctr-electronics.com and generates index files
for the CTRE MCP plugin.

Usage:
    python -m wpilib_mcp.plugins.ctre.build_index
    
    # Or from the plugin directory:
    python build_index.py
"""

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

# Handle both module and direct execution
try:
    from wpilib_mcp.utils.indexer import BaseIndexBuilder
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from wpilib_mcp.utils.indexer import BaseIndexBuilder


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CTREIndexBuilder(BaseIndexBuilder):
    """Index builder for CTRE Phoenix 6 documentation."""
    
    def __init__(self, version: str = "stable"):
        super().__init__(
            vendor="ctre",
            base_url="https://v6.docs.ctr-electronics.com",
            max_pages=250,
            max_depth=4,
            rate_limit=0.15
        )
        self.doc_version = version
    
    @property
    def start_urls(self) -> list[str]:
        base = f"https://v6.docs.ctr-electronics.com/en/{self.doc_version}/docs"
        return [
            f"{base}/hardware-reference/talonfx/index.html",
            f"{base}/hardware-reference/cancoder/index.html",
            f"{base}/hardware-reference/pigeon2/index.html",
            f"{base}/api-reference/index.html",
            f"{base}/application-notes/index.html",
            f"{base}/tuner/index.html",
        ]
    
    def should_crawl(self, url: str) -> bool:
        """Only crawl CTRE Phoenix 6 docs."""
        if "v6.docs.ctr-electronics.com" not in url:
            return False
        
        # Must be in the docs section
        if "/docs/" not in url:
            return False
        
        # Exclude non-content pages
        exclude_patterns = [
            r"_sources/",
            r"genindex",
            r"search\.html",
            r"py-modindex",
            r"/_modules/",
            r"/api-reference/api/",  # Skip raw API docs
        ]
        for pattern in exclude_patterns:
            if re.search(pattern, url):
                return False
        
        return True
    
    def extract_section(self, soup: BeautifulSoup, url: str) -> str:
        """Extract section from URL path."""
        if "/talonfx/" in url:
            return "TalonFX"
        elif "/cancoder/" in url:
            return "CANcoder"
        elif "/pigeon" in url:
            return "Pigeon 2"
        elif "/kraken/" in url:
            return "Kraken X60"
        elif "/canivore/" in url:
            return "CANivore"
        elif "/tuner/" in url:
            return "Phoenix Tuner X"
        elif "/application-notes/" in url:
            return "Application Notes"
        elif "/api-reference/" in url:
            return "API Reference"
        elif "/mechanisms/" in url:
            return "Mechanisms"
        elif "/simulation/" in url:
            return "Simulation"
        return "General"
    
    def extract_language(self, soup: BeautifulSoup, url: str) -> str:
        """Extract language from Phoenix docs."""
        # Check for language tabs (Phoenix 6 uses Sphinx tabs)
        tabs = soup.find_all(class_=re.compile(r"sphinx-tabs|tab-label"))
        if tabs:
            return "All"  # Has multi-language examples
        
        # Check code blocks
        code_blocks = soup.find_all(["code", "pre"])
        code_text = " ".join(c.get_text() for c in code_blocks)
        
        has_java = "import com.ctre" in code_text or "TalonFX(" in code_text
        has_cpp = "ctre::phoenix" in code_text or "#include" in code_text
        
        if has_java and has_cpp:
            return "All"
        elif has_java:
            return "Java"
        elif has_cpp:
            return "C++"
        
        return "All"
    
    def extract_content(self, soup: BeautifulSoup, url: str) -> str:
        """Extract content from CTRE's Sphinx-based docs."""
        # Remove navigation and boilerplate
        for selector in [
            "nav", "header", "footer", ".sidebar", ".sphinxsidebar",
            ".related", ".breadcrumb", ".prev-next-bottom",
            "script", "style", ".headerlink", ".edit-link"
        ]:
            for elem in soup.select(selector):
                elem.decompose()
        
        # Find main content
        main = (
            soup.find("main") or
            soup.find(class_="document") or
            soup.find(class_="body") or
            soup.find(role="main") or
            soup.body
        )
        
        if main is None:
            return ""
        
        text = main.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


async def main():
    parser = argparse.ArgumentParser(
        description="Build CTRE Phoenix documentation index"
    )
    parser.add_argument(
        "--version",
        default="stable",
        help="Phoenix 6 docs version (default: stable)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: data/index.json)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine output path
    data_dir = Path(__file__).parent / "data"
    output_path = args.output or (data_dir / "index.json")
    
    # Build index
    builder = CTREIndexBuilder(version=args.version)
    await builder.build_and_save("phoenix6", output_path)
    
    print(f"\n✓ CTRE index saved to {output_path}")
    print(f"  Pages indexed: {len(builder.pages)}")


if __name__ == "__main__":
    asyncio.run(main())




