#!/usr/bin/env python3
"""
Build documentation index for WPILib.

This script crawls docs.wpilib.org and generates index files
for the WPILib MCP plugin.

Usage:
    python -m wpilib_mcp.plugins.wpilib.build_index --version 2025
    
    # Or from the plugin directory:
    python build_index.py --version 2025
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


class WPILibIndexBuilder(BaseIndexBuilder):
    """Index builder for WPILib documentation."""
    
    def __init__(self, version: str = "stable"):
        super().__init__(
            vendor="wpilib",
            base_url="https://docs.wpilib.org",
            max_pages=300,
            max_depth=4,
            rate_limit=0.15
        )
        self.version = version
        self._version_path = f"/en/{version}/docs/"
    
    @property
    def start_urls(self) -> list[str]:
        base = f"https://docs.wpilib.org/en/{self.version}/docs"
        return [
            f"{base}/software/commandbased/index.html",
            f"{base}/software/advanced-controls/index.html",
            f"{base}/software/hardware-apis/index.html",
            f"{base}/software/kinematics-and-odometry/index.html",
            f"{base}/software/pathplanning/index.html",
            f"{base}/software/networktables/index.html",
            f"{base}/software/basic-programming/index.html",
            f"{base}/software/can-devices/index.html",
            f"{base}/software/vision-processing/index.html",
        ]
    
    def should_crawl(self, url: str) -> bool:
        """Only crawl WPILib software docs."""
        # Must be on docs.wpilib.org
        if "docs.wpilib.org" not in url:
            return False
        
        # Must be in the docs/software section
        if "/docs/software/" not in url and "/docs/controls/" not in url:
            return False
        
        # Exclude non-content pages
        exclude_patterns = [
            r"_sources/",
            r"genindex",
            r"search\.html",
            r"py-modindex",
            r"/_modules/",
        ]
        for pattern in exclude_patterns:
            if re.search(pattern, url):
                return False
        
        return True
    
    def extract_section(self, soup: BeautifulSoup, url: str) -> str:
        """Extract section from URL path."""
        if "commandbased" in url:
            return "Command-Based Programming"
        elif "advanced-controls" in url or "controllers" in url:
            return "Advanced Controls"
        elif "hardware-apis" in url:
            return "Hardware APIs"
        elif "kinematics" in url or "odometry" in url:
            return "Kinematics and Odometry"
        elif "pathplanning" in url or "trajectory" in url:
            return "Path Planning"
        elif "networktables" in url:
            return "NetworkTables"
        elif "vision" in url:
            return "Vision Processing"
        elif "can-devices" in url:
            return "CAN Devices"
        elif "basic-programming" in url:
            return "Basic Programming"
        elif "wpimath" in url:
            return "WPIMath"
        return "General"
    
    def extract_language(self, soup: BeautifulSoup, url: str) -> str:
        """Extract language from page content/tabs."""
        # Check for language-specific tabs
        tabs = soup.find_all(class_=re.compile(r"tab-label|sphinx-tabs-tab"))
        tab_text = " ".join(t.get_text() for t in tabs).lower()
        
        # Check page content
        content_text = soup.get_text().lower()[:2000]
        
        # If page has tabs for multiple languages, it's "All"
        has_java = "java" in tab_text or "java" in content_text
        has_python = "python" in tab_text or "python" in content_text
        has_cpp = "c++" in tab_text or "cpp" in content_text
        
        if sum([has_java, has_python, has_cpp]) > 1:
            return "All"
        elif has_java and not has_python and not has_cpp:
            return "Java"
        elif has_python and not has_java and not has_cpp:
            return "Python"
        elif has_cpp and not has_java and not has_python:
            return "C++"
        
        return "All"
    
    def extract_content(self, soup: BeautifulSoup, url: str) -> str:
        """Extract content, handling WPILib's specific structure."""
        # Remove navigation and boilerplate
        for selector in [
            "nav", "header", "footer", ".sidebar", ".sphinxsidebar",
            ".related", ".breadcrumb", ".edit-page-link", ".prev-next-bottom",
            "script", "style", ".headerlink"
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
        
        # Get text
        text = main.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


async def main():
    parser = argparse.ArgumentParser(
        description="Build WPILib documentation index"
    )
    parser.add_argument(
        "--version",
        default="stable",
        help="WPILib version to index (default: stable)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: data/index_{version}.json)"
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
    output_path = args.output or (data_dir / f"index_{args.version}.json")
    
    # Build index
    builder = WPILibIndexBuilder(version=args.version)
    await builder.build_and_save(args.version, output_path)
    
    print(f"\n✓ WPILib index saved to {output_path}")
    print(f"  Pages indexed: {len(builder.pages)}")


if __name__ == "__main__":
    asyncio.run(main())



