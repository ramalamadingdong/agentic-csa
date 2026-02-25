#!/usr/bin/env python3
"""
Build documentation index for Redux Robotics.

Uses the llms.txt sitemap endpoint at docs.reduxrobotics.com to discover pages
and fetches markdown source files directly when available.

Usage:
    python -m wpilib_mcp.plugins.redux.build_index

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

BASE_URL = "https://docs.reduxrobotics.com"
SITEMAP_URL = f"{BASE_URL}/llms.txt?type=sitemap"
RATE_LIMIT = 0.2


def should_crawl(url: str) -> bool:
    """Only index Redux docs pages from the docs host."""
    if not url.startswith(BASE_URL):
        return False

    exclude_patterns = [r"/api/", r"/changelog", r"/release-notes"]
    return not any(re.search(pattern, url) for pattern in exclude_patterns)


def extract_section(url: str) -> str:
    """Determine documentation section from URL path."""
    if "/canandcoder/" in url:
        return "Canandcoder"
    if "/canandgyro/" in url:
        return "Canandgyro"
    if "/canandcolor/" in url:
        return "Canandcolor"
    if "/canandmag/" in url:
        return "Canandmag"
    if "/reduxlib/" in url:
        return "ReduxLib"
    if "/tutorials/" in url:
        return "Tutorials"
    return "General"


def detect_language_from_html(soup: BeautifulSoup) -> str:
    """Detect language from code blocks in HTML pages."""
    code_blocks = soup.find_all(["code", "pre"])
    code_text = " ".join(block.get_text(" ", strip=True) for block in code_blocks)

    has_java = "import com.reduxrobotics" in code_text
    has_cpp = "redux::" in code_text or "#include" in code_text
    has_python = "import reduxrobotics" in code_text

    count = sum([has_java, has_cpp, has_python])
    if count > 1:
        return "All"
    if has_java:
        return "Java"
    if has_cpp:
        return "C++"
    if has_python:
        return "Python"
    return "All"


def extract_html_content(soup: BeautifulSoup) -> str:
    """Extract content from HTML documentation pages."""
    for selector in [
        "nav", "header", "footer", "script", "style",
        ".sidebar", ".table-of-contents",
    ]:
        for element in soup.select(selector):
            element.decompose()

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(class_="content")
        or soup.body
    )
    if main is None:
        return ""

    text = main.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def title_from_url(url: str) -> str:
    """Generate a fallback title from URL slug."""
    slug = url.rstrip("/").split("/")[-1].removesuffix(".md")
    if slug == "" or slug == "index":
        return "Redux Robotics Documentation"
    return slug.replace("-", " ").replace("_", " ").title()


def create_preview(content: str, max_length: int = 300) -> str:
    """Create a preview snippet from content."""
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


def parse_sitemap(text: str) -> list[str]:
    """Parse a plain-text sitemap containing one URL per line."""
    urls: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


async def build(version: str = "latest") -> dict:
    """Fetch llms sitemap and build the Redux documentation index."""
    pages: list[PageData] = []

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "WPILib-MCP-redux-Indexer/1.0"},
    ) as client:
        logger.info(f"Fetching {SITEMAP_URL}")
        try:
            resp = await client.get(SITEMAP_URL)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch Redux sitemap: {e}")
            return {
                "vendor": "redux",
                "version": version,
                "built_at": datetime.now().isoformat(),
                "pages": [],
            }

        urls = parse_sitemap(resp.text)
        logger.info(f"Found {len(urls)} entries in Redux sitemap")

        for source_url in urls:
            if not should_crawl(source_url):
                continue

            await asyncio.sleep(RATE_LIMIT)
            try:
                page_resp = await client.get(source_url)
                page_resp.raise_for_status()
            except Exception as e:
                logger.warning(f"Could not fetch {source_url}: {e}")
                continue

            raw_content = page_resp.text
            if len(raw_content.strip()) < 50:
                continue

            section = extract_section(source_url)
            is_markdown = source_url.endswith(".md")

            if is_markdown:
                content = raw_content
                title = extract_md_title(content) or title_from_url(source_url)
                language = detect_md_language(content)
                canonical_url = source_url.removesuffix(".md")
            else:
                soup = BeautifulSoup(raw_content, "html.parser")
                content = extract_html_content(soup)
                title = (
                    (soup.find("h1").get_text(strip=True) if soup.find("h1") else None)
                    or (soup.title.string.strip() if soup.title and soup.title.string else None)
                    or title_from_url(source_url)
                )
                language = detect_language_from_html(soup)
                canonical_url = source_url

            if len(content.strip()) < 100:
                continue

            pages.append(
                PageData(
                    url=canonical_url,
                    title=title,
                    section=section,
                    language=language,
                    content=content,
                    content_preview=create_preview(content),
                )
            )
            logger.info(f"Indexed: {title}")

    logger.info(f"Indexed {len(pages)} pages for redux")
    return {
        "vendor": "redux",
        "version": version,
        "built_at": datetime.now().isoformat(),
        "pages": [asdict(page) for page in pages],
    }


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
    
    data_dir = Path(__file__).parent / "data"
    output_path = args.output or (data_dir / "index.json")

    index = await build("latest")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Redux index saved to {output_path}")
    print(f"  Pages indexed: {len(index['pages'])}")


if __name__ == "__main__":
    asyncio.run(main())
