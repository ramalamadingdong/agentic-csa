#!/usr/bin/env python3
"""
Build documentation index for PhotonVision.

Discovers pages by crawling HTML, then fetches each page's
_sources/*.md.txt Sphinx source file for clean MyST Markdown content.
Falls back to HTML extraction if the source file is unavailable.

Usage:
    python -m wpilib_mcp.plugins.photonvision.build_index

    # Or from the plugin directory:
    python build_index.py
"""

import argparse
import asyncio
import json
import logging
import re
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# Handle both module and direct execution
try:
    from wpilib_mcp.utils.indexer import PageData
    from wpilib_mcp.utils.markdown import extract_md_title, detect_md_language
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from wpilib_mcp.utils.indexer import PageData
    from wpilib_mcp.utils.markdown import extract_md_title, detect_md_language


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = "https://docs.photonvision.org"
MAX_PAGES = 300
MAX_DEPTH = 5
RATE_LIMIT = 0.2

START_URLS = [
    "https://docs.photonvision.org/en/latest/",
    "https://docs.photonvision.org/en/latest/docs/quick-start/index.html",
    "https://docs.photonvision.org/en/latest/docs/hardware/index.html",
    "https://docs.photonvision.org/en/latest/docs/installation/index.html",
    "https://docs.photonvision.org/en/latest/docs/pipelines/index.html",
    "https://docs.photonvision.org/en/latest/docs/apriltag-pipelines/index.html",
    "https://docs.photonvision.org/en/latest/docs/reflectiveAndShape/index.html",
    "https://docs.photonvision.org/en/latest/docs/objectDetection/index.html",
    "https://docs.photonvision.org/en/latest/docs/programming/photonlib/index.html",
    "https://docs.photonvision.org/en/latest/docs/simulation/index.html",
    "https://docs.photonvision.org/en/latest/docs/integration/index.html",
    "https://docs.photonvision.org/en/latest/docs/examples/index.html",
    "https://docs.photonvision.org/en/latest/docs/troubleshooting/index.html",
    "https://docs.photonvision.org/en/latest/docs/additional-resources/index.html",
]


def to_sources_url(url: str) -> str:
    """
    Convert a PhotonVision HTML page URL to its Sphinx _sources .md.txt URL.

    Example:
      .../en/latest/docs/programming/photonlib/index.html
      -> .../en/latest/_sources/docs/programming/photonlib/index.md.txt
    """
    parsed = urlparse(url)
    path = parsed.path

    marker = "/en/latest/"
    if marker not in path:
        return ""

    prefix, rest = path.split(marker, 1)
    rest = rest.rstrip("/")
    if rest.endswith(".html"):
        rest = rest[:-5]
    elif not rest:
        rest = "index"

    sources_path = f"{prefix}{marker}_sources/{rest}.md.txt"
    return parsed._replace(path=sources_path).geturl()


def should_crawl(url: str) -> bool:
    """Only crawl PhotonVision docs pages."""
    if "docs.photonvision.org" not in url:
        return False
    if "/en/latest/" not in url:
        return False
    exclude = [r"\?", r"/_", r"/genindex", r"/search\.html",
               r"/py-modindex", r"\.zip$", r"\.pdf$",
               r"\.png$", r"\.jpg$", r"\.svg$"]
    return not any(re.search(p, url) for p in exclude)


def extract_section(url: str) -> str:
    """Determine documentation section from URL path."""
    u = url.lower()
    if "/quick-start/" in u or "/about" in u:
        return "Getting Started"
    elif "/hardware/" in u:
        return "Hardware Selection"
    elif "/installation/" in u:
        return "Installation"
    elif "/camera" in u and "config" in u:
        return "Camera Configuration"
    elif "/pipelines/" in u:
        return "Pipelines"
    elif "/apriltag" in u:
        return "AprilTag Detection"
    elif "/reflective" in u or "/shape" in u:
        return "Reflective & Shape Detection"
    elif "/objectdetection" in u:
        return "Object Detection"
    elif "/calibrat" in u:
        return "Camera Calibration"
    elif "/photonlib/" in u:
        return "PhotonLib"
    elif "/simulation/" in u:
        return "Simulation"
    elif "/integration/" in u:
        return "Robot Integration"
    elif "/examples/" in u:
        return "Code Examples"
    elif "/troubleshooting/" in u:
        return "Troubleshooting"
    elif "/contributing/" in u:
        return "Contributing"
    elif "/additional-resources/" in u or "/best-practices" in u:
        return "Additional Resources"
    return "General"


def extract_links(soup: BeautifulSoup, page_url: str) -> list[str]:
    """Extract in-domain links from an HTML page."""
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("#", "mailto:", "javascript:")):
            continue
        full = urljoin(page_url, href).split("#")[0]
        if urlparse(full).netloc == urlparse(BASE_URL).netloc:
            links.append(full)
    return list(set(links))


def create_preview(content: str, max_length: int = 300) -> str:
    if len(content) <= max_length:
        return content
    preview = content[:max_length]
    last_period = preview.rfind(". ")
    if last_period > max_length * 0.5:
        return preview[:last_period + 1]
    last_space = preview.rfind(" ")
    if last_space > max_length * 0.7:
        return preview[:last_space] + "..."
    return preview + "..."


def extract_html_content(soup: BeautifulSoup) -> str:
    """Fallback: extract plain text from HTML."""
    for selector in [
        "nav", "header", "footer", ".sidebar", ".sidebar-drawer",
        ".toc-drawer", ".mobile-header", "script", "style",
        ".edit-page", ".page-nav", ".prev-next-area", ".footer-article",
        ".bd-sidebar", ".bd-toc"
    ]:
        for elem in soup.select(selector):
            elem.decompose()

    main = (
        soup.find("article", class_="bd-article") or
        soup.find("main", id="main-content") or
        soup.find("div", class_="bd-content") or
        soup.find("main") or
        soup.find("article") or
        soup.body
    )
    if main is None:
        return ""
    text = main.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


async def build(version: str = "latest") -> dict:
    """Crawl HTML for link discovery, then fetch _sources/*.md.txt for content."""
    pages: list[PageData] = []
    visited: set[str] = set()
    discovered: list[str] = []

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "WPILib-MCP-photonvision-Indexer/1.0"}
    ) as client:

        # --- Phase 1: discover all page URLs via HTML crawl ---
        async def crawl_links(url: str, depth: int) -> None:
            if depth > MAX_DEPTH or url in visited or len(discovered) >= MAX_PAGES:
                return
            if not should_crawl(url):
                return
            visited.add(url)
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                discovered.append(url)
                for link in extract_links(soup, url):
                    await crawl_links(link, depth + 1)
                    await asyncio.sleep(RATE_LIMIT)
            except Exception as e:
                logger.warning(f"Link discovery error {url}: {e}")

        for start in START_URLS:
            await crawl_links(start, depth=0)
            if len(discovered) >= MAX_PAGES:
                break

        logger.info(f"Discovered {len(discovered)} pages")

        # --- Phase 2: fetch _sources/*.md.txt for each page ---
        for html_url in discovered:
            await asyncio.sleep(RATE_LIMIT)
            sources_url = to_sources_url(html_url)

            markdown = None
            if sources_url:
                try:
                    resp = await client.get(sources_url)
                    resp.raise_for_status()
                    markdown = resp.text
                    logger.debug(f"Got markdown source: {sources_url}")
                except Exception:
                    pass

            if markdown and len(markdown.strip()) >= 100:
                title = extract_md_title(markdown) or html_url.split("/")[-1]
                language = detect_md_language(markdown)
                content = markdown
            else:
                # Fall back to HTML extraction
                try:
                    resp = await client.get(html_url)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "lxml")
                    content = extract_html_content(soup)
                    h1 = soup.find("h1")
                    title = (
                        (soup.title.string.strip() if soup.title else None) or
                        (h1.get_text(strip=True) if h1 else None) or
                        html_url.split("/")[-1]
                    )
                    language = "All"
                except Exception as e:
                    logger.warning(f"HTML fallback failed {html_url}: {e}")
                    continue

            if len(content) < 100:
                continue

            section = extract_section(html_url)
            pages.append(PageData(
                url=html_url,
                title=title,
                section=section,
                language=language,
                content=content,
                content_preview=create_preview(content),
            ))
            logger.info(f"Indexed: {title}")

    logger.info(f"Indexed {len(pages)} pages for photonvision")
    return {
        "vendor": "photonvision",
        "version": version,
        "built_at": datetime.now().isoformat(),
        "pages": [asdict(p) for p in pages],
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Build PhotonVision documentation index"
    )
    parser.add_argument("--output", type=Path,
                        help="Output file path (default: data/index.json)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    data_dir = Path(__file__).parent / "data"
    output_path = args.output or (data_dir / "index.json")

    index = await build("latest")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\n✓ PhotonVision index saved to {output_path}")
    print(f"  Pages indexed: {len(index['pages'])}")


if __name__ == "__main__":
    asyncio.run(main())
