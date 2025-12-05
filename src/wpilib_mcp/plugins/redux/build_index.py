#!/usr/bin/env python3
"""
Build documentation index for Redux Robotics.

This script crawls docs.reduxrobotics.com and generates index files
for the Redux MCP plugin.

Usage:
    python -m wpilib_mcp.plugins.redux.build_index
    
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


class ReduxIndexBuilder(BaseIndexBuilder):
    """Index builder for Redux Robotics documentation."""
    
    def __init__(self):
        super().__init__(
            vendor="redux",
            base_url="https://docs.reduxrobotics.com",
            max_pages=100,
            max_depth=3,
            rate_limit=0.2
        )
    
    @property
    def start_urls(self) -> list[str]:
        return [
            "https://docs.reduxrobotics.com/canandcoder/",
            "https://docs.reduxrobotics.com/canandgyro/",
            "https://docs.reduxrobotics.com/reduxlib/",
        ]
    
    def should_crawl(self, url: str) -> bool:
        """Only crawl Redux docs."""
        if "docs.reduxrobotics.com" not in url:
            return False
        
        # Focus on product documentation
        allowed_sections = [
            "/canandcoder/",
            "/canandgyro/",
            "/reduxlib/",
            "/canandcolor/",
        ]
        
        if not any(section in url for section in allowed_sections):
            # Allow root pages
            if url.rstrip("/") != "https://docs.reduxrobotics.com":
                return False
        
        # Exclude non-content
        exclude_patterns = [
            r"\?",
            r"/changelog",
            r"/api/",
        ]
        for pattern in exclude_patterns:
            if re.search(pattern, url):
                return False
        
        return True
    
    def extract_section(self, soup: BeautifulSoup, url: str) -> str:
        """Extract section from URL path."""
        if "/canandcoder/" in url:
            return "Canandcoder"
        elif "/canandgyro/" in url:
            return "Canandgyro"
        elif "/canandcolor/" in url:
            return "Canandcolor"
        elif "/reduxlib/" in url:
            return "ReduxLib"
        return "General"
    
    def extract_language(self, soup: BeautifulSoup, url: str) -> str:
        """Extract language from Redux docs."""
        code_blocks = soup.find_all(["code", "pre"])
        code_text = " ".join(c.get_text() for c in code_blocks)
        
        has_java = "import com.reduxrobotics" in code_text
        has_cpp = "redux::" in code_text or "#include" in code_text
        
        if has_java and has_cpp:
            return "All"
        elif has_java:
            return "Java"
        elif has_cpp:
            return "C++"
        
        return "All"
    
    def extract_content(self, soup: BeautifulSoup, url: str) -> str:
        """Extract content from Redux documentation."""
        # Remove navigation
        for selector in [
            "nav", "header", "footer", ".sidebar",
            ".table-of-contents", "script", "style"
        ]:
            for elem in soup.select(selector):
                elem.decompose()
        
        main = (
            soup.find("main") or
            soup.find("article") or
            soup.find(class_="content") or
            soup.body
        )
        
        if main is None:
            return ""
        
        text = main.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


async def main():
    parser = argparse.ArgumentParser(
        description="Build Redux Robotics documentation index"
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
    builder = ReduxIndexBuilder()
    await builder.build_and_save("latest", output_path)
    
    print(f"\n✓ Redux index saved to {output_path}")
    print(f"  Pages indexed: {len(builder.pages)}")


if __name__ == "__main__":
    asyncio.run(main())




