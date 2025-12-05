#!/usr/bin/env python3
"""
Build documentation index for REV Robotics.

This script crawls docs.revrobotics.com and generates index files
for the REV MCP plugin.

Usage:
    python -m wpilib_mcp.plugins.rev.build_index
    
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


class REVIndexBuilder(BaseIndexBuilder):
    """Index builder for REV Robotics documentation."""
    
    def __init__(self):
        super().__init__(
            vendor="rev",
            base_url="https://docs.revrobotics.com",
            max_pages=200,
            max_depth=4,
            rate_limit=0.2
        )
    
    @property
    def start_urls(self) -> list[str]:
        return [
            "https://docs.revrobotics.com/brushless/spark-max/overview",
            "https://docs.revrobotics.com/brushless/spark-flex/overview",
            "https://docs.revrobotics.com/brushless/neo/neo-motor",
            "https://docs.revrobotics.com/brushless/neo/neo-vortex",
            "https://docs.revrobotics.com/through-bore-encoder/overview",
            "https://docs.revrobotics.com/rev-hardware-client/getting-started",
        ]
    
    def should_crawl(self, url: str) -> bool:
        """Only crawl REV docs relevant to FRC."""
        if "docs.revrobotics.com" not in url:
            return False
        
        # Focus on FRC-relevant sections
        allowed_sections = [
            "/brushless/",
            "/through-bore-encoder/",
            "/rev-hardware-client/",
            "/ion/",  # REV ION
        ]
        
        if not any(section in url for section in allowed_sections):
            return False
        
        # Exclude non-content pages
        exclude_patterns = [
            r"\?",
            r"/api/",
            r"/changelog",
            r"/release-notes",
        ]
        for pattern in exclude_patterns:
            if re.search(pattern, url):
                return False
        
        return True
    
    def extract_section(self, soup: BeautifulSoup, url: str) -> str:
        """Extract section from URL path."""
        if "/spark-max/" in url:
            return "SPARK MAX"
        elif "/spark-flex/" in url:
            return "SPARK Flex"
        elif "/neo-motor" in url or "/neo-550" in url:
            return "NEO Motors"
        elif "/neo-vortex" in url:
            return "NEO Vortex"
        elif "/through-bore-encoder/" in url:
            return "Through Bore Encoder"
        elif "/rev-hardware-client/" in url:
            return "REV Hardware Client"
        elif "/ion/" in url:
            return "REV ION"
        elif "/revlib" in url.lower():
            return "REVLib"
        return "General"
    
    def extract_language(self, soup: BeautifulSoup, url: str) -> str:
        """REV docs are generally language-agnostic or Java/C++ focused."""
        # Check for code blocks
        code_blocks = soup.find_all("code")
        code_text = " ".join(c.get_text() for c in code_blocks).lower()
        
        # Check for language indicators
        has_java = "import com.rev" in code_text or "cansparkmax" in code_text.lower()
        has_cpp = "#include" in code_text or "rev::" in code_text
        
        if has_java and not has_cpp:
            return "Java"
        elif has_cpp and not has_java:
            return "C++"
        
        return "All"
    
    def extract_content(self, soup: BeautifulSoup, url: str) -> str:
        """Extract content from REV's documentation structure."""
        # Remove navigation elements
        for selector in [
            "nav", "header", "footer", ".sidebar", ".menu",
            ".table-of-contents", ".toc", "script", "style",
            ".edit-page", ".page-nav"
        ]:
            for elem in soup.select(selector):
                elem.decompose()
        
        # Find main content - REV uses different structures
        main = (
            soup.find("main") or
            soup.find("article") or
            soup.find(class_="content") or
            soup.find(class_="markdown-body") or
            soup.body
        )
        
        if main is None:
            return ""
        
        text = main.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


async def main():
    parser = argparse.ArgumentParser(
        description="Build REV Robotics documentation index"
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
    builder = REVIndexBuilder()
    await builder.build_and_save("latest", output_path)
    
    print(f"\n✓ REV index saved to {output_path}")
    print(f"  Pages indexed: {len(builder.pages)}")


if __name__ == "__main__":
    asyncio.run(main())




