#!/usr/bin/env python3
"""
Build documentation index for PhotonVision.

This script crawls docs.photonvision.org and generates index files
for the PhotonVision MCP plugin.

Usage:
    python -m wpilib_mcp.plugins.photonvision.build_index
    
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


class PhotonVisionIndexBuilder(BaseIndexBuilder):
    """Index builder for PhotonVision documentation."""
    
    def __init__(self):
        super().__init__(
            vendor="photonvision",
            base_url="https://docs.photonvision.org",
            max_pages=300,
            max_depth=5,
            rate_limit=0.2
        )
    
    @property
    def start_urls(self) -> list[str]:
        return [
            # Main landing page
            "https://docs.photonvision.org/en/latest/",
            # Getting Started section
            "https://docs.photonvision.org/en/latest/docs/quick-start/index.html",
            "https://docs.photonvision.org/en/latest/docs/hardware/index.html",
            "https://docs.photonvision.org/en/latest/docs/installation/index.html",
            # Pipeline Tuning
            "https://docs.photonvision.org/en/latest/docs/pipelines/index.html",
            "https://docs.photonvision.org/en/latest/docs/apriltag-pipelines/index.html",
            "https://docs.photonvision.org/en/latest/docs/reflectiveAndShape/index.html",
            "https://docs.photonvision.org/en/latest/docs/objectDetection/index.html",
            # Programming Reference
            "https://docs.photonvision.org/en/latest/docs/programming/photonlib/index.html",
            "https://docs.photonvision.org/en/latest/docs/simulation/index.html",
            "https://docs.photonvision.org/en/latest/docs/integration/index.html",
            "https://docs.photonvision.org/en/latest/docs/examples/index.html",
            # Additional Resources
            "https://docs.photonvision.org/en/latest/docs/troubleshooting/index.html",
            "https://docs.photonvision.org/en/latest/docs/additional-resources/index.html",
        ]
    
    def should_crawl(self, url: str) -> bool:
        """Only crawl PhotonVision docs."""
        if "docs.photonvision.org" not in url:
            return False
        
        # Must be in /en/latest/ path
        if "/en/latest/" not in url:
            return False
        
        # Exclude non-content pages
        exclude_patterns = [
            r"\?",
            r"/_",
            r"/genindex",
            r"/search\.html",
            r"/py-modindex",
            r"\.zip$",
            r"\.pdf$",
            r"\.png$",
            r"\.jpg$",
            r"\.svg$",
        ]
        for pattern in exclude_patterns:
            if re.search(pattern, url):
                return False
        
        return True
    
    def extract_section(self, soup: BeautifulSoup, url: str) -> str:
        """Extract section from URL path."""
        url_lower = url.lower()
        
        # Getting Started sections
        if "/quick-start/" in url_lower or "/about" in url_lower:
            return "Getting Started"
        elif "/hardware/" in url_lower:
            return "Hardware Selection"
        elif "/installation/" in url_lower:
            return "Installation"
        elif "/camera" in url_lower and "config" in url_lower:
            return "Camera Configuration"
        
        # Pipeline Tuning sections
        elif "/pipelines/" in url_lower:
            return "Pipelines"
        elif "/apriltag" in url_lower:
            return "AprilTag Detection"
        elif "/reflective" in url_lower or "/shape" in url_lower:
            return "Reflective & Shape Detection"
        elif "/objectdetection" in url_lower:
            return "Object Detection"
        elif "/calibrat" in url_lower:
            return "Camera Calibration"
        
        # Programming Reference sections
        elif "/photonlib/" in url_lower:
            return "PhotonLib"
        elif "/simulation/" in url_lower:
            return "Simulation"
        elif "/integration/" in url_lower:
            return "Robot Integration"
        elif "/examples/" in url_lower:
            return "Code Examples"
        
        # Additional Resources
        elif "/troubleshooting/" in url_lower:
            return "Troubleshooting"
        elif "/contributing/" in url_lower:
            return "Contributing"
        elif "/additional-resources/" in url_lower or "/best-practices" in url_lower:
            return "Additional Resources"
        
        return "General"
    
    def extract_language(self, soup: BeautifulSoup, url: str) -> str:
        """Detect programming language from code blocks."""
        # Look for language-specific tabs or code blocks
        page_text = soup.get_text().lower()
        
        # Check for language tabs (PhotonVision uses tabs for multi-language examples)
        tabs = soup.find_all(class_=re.compile(r"tab|language", re.I))
        tab_text = " ".join(t.get_text().lower() for t in tabs)
        
        # Check code blocks
        code_blocks = soup.find_all("code")
        code_text = " ".join(c.get_text() for c in code_blocks).lower()
        
        # Language detection
        has_java = (
            "import org.photonvision" in code_text or
            "photoncamera" in code_text and "new " in code_text or
            'class="language-java"' in str(soup).lower()
        )
        has_cpp = (
            "#include" in code_text and "photon" in code_text or
            "photon::" in code_text or
            'class="language-cpp"' in str(soup).lower() or
            'class="language-c++"' in str(soup).lower()
        )
        has_python = (
            "from photonlibpy" in code_text or
            "import photonlibpy" in code_text or
            'class="language-python"' in str(soup).lower()
        )
        
        # If multiple languages or tabs present, mark as All
        langs_found = sum([has_java, has_cpp, has_python])
        if langs_found > 1 or "java" in tab_text and "c++" in tab_text:
            return "All"
        elif has_java:
            return "Java"
        elif has_cpp:
            return "C++"
        elif has_python:
            return "Python"
        
        return "All"
    
    def extract_content(self, soup: BeautifulSoup, url: str) -> str:
        """Extract content from PhotonVision's Sphinx documentation structure."""
        # Remove navigation elements
        for selector in [
            "nav", "header", "footer", 
            ".sidebar", ".sidebar-drawer",
            ".toc-drawer", ".mobile-header",
            "script", "style",
            ".edit-page", ".page-nav",
            ".prev-next-area", ".footer-article",
            ".bd-sidebar", ".bd-toc"
        ]:
            for elem in soup.select(selector):
                elem.decompose()
        
        # Find main content - Sphinx/Furo theme structure
        main = (
            soup.find("article", class_="bd-article") or
            soup.find("main", id="main-content") or
            soup.find("div", class_="bd-content") or
            soup.find("main") or
            soup.find("article") or
            soup.find(class_="content") or
            soup.find(class_="document") or
            soup.body
        )
        
        if main is None:
            return ""
        
        text = main.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


async def main():
    parser = argparse.ArgumentParser(
        description="Build PhotonVision documentation index"
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
    builder = PhotonVisionIndexBuilder()
    await builder.build_and_save("latest", output_path)
    
    print(f"\nPhotonVision index saved to {output_path}")
    print(f"  Pages indexed: {len(builder.pages)}")


if __name__ == "__main__":
    asyncio.run(main())

