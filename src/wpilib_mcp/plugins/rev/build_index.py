#!/usr/bin/env python3
"""
Build documentation index for REV Robotics.

Uses the llms.txt index at docs.revrobotics.com to discover pages and
fetches their .md source files directly — no HTML parsing required.

Usage:
    python -m wpilib_mcp.plugins.rev.build_index

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

BASE_URL = "https://docs.revrobotics.com"
LLMS_TXT_URL = f"{BASE_URL}/llms.txt"
RATE_LIMIT = 0.2


def should_crawl(url: str) -> bool:
    """Only index REV pages relevant to FRC."""
    if BASE_URL not in url:
        return False

    allowed_sections = [
        "/brushless/",
        "/through-bore-encoder/",
        "/rev-hardware-client/",
        "/ion/",
    ]
    if not any(s in url for s in allowed_sections):
        return False

    exclude_patterns = [r"\?", r"/api/", r"/changelog", r"/release-notes"]
    return not any(re.search(p, url) for p in exclude_patterns)


def extract_section(url: str) -> str:
    """Determine documentation section from URL path."""
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


def parse_llms_txt(text: str) -> list[tuple[str, str]]:
    """
    Parse llms.txt and return (title, absolute_url) pairs for .md links.

    Handles lines like:  - [Page Title](/path/to/page.md)
    """
    results = []
    for line in text.splitlines():
        match = re.match(r"\s*-\s*\[([^\]]+)\]\((/[^\)]+\.md)\)", line)
        if match:
            title, path = match.group(1), match.group(2)
            results.append((title, BASE_URL + path))
    return results


async def build(version: str = "latest") -> dict:
    """Fetch llms.txt, then fetch each .md page and build the index."""
    pages: list[PageData] = []

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "WPILib-MCP-rev-Indexer/1.0"}
    ) as client:
        # Step 1: fetch the URL list from llms.txt
        logger.info(f"Fetching {LLMS_TXT_URL}")
        try:
            resp = await client.get(LLMS_TXT_URL)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch llms.txt: {e}")
            return {"vendor": "rev", "version": version,
                    "built_at": datetime.now().isoformat(), "pages": []}

        entries = parse_llms_txt(resp.text)
        logger.info(f"Found {len(entries)} entries in llms.txt")

        # Step 2: fetch each .md file
        for llms_title, md_url in entries:
            if not should_crawl(md_url):
                continue

            await asyncio.sleep(RATE_LIMIT)
            try:
                logger.debug(f"Fetching: {md_url}")
                md_resp = await client.get(md_url)
                md_resp.raise_for_status()
                markdown = md_resp.text
            except Exception as e:
                logger.warning(f"Could not fetch {md_url}: {e}")
                continue

            if len(markdown.strip()) < 100:
                continue

            title = extract_md_title(markdown) or llms_title
            section = extract_section(md_url)
            language = detect_md_language(markdown)
            preview = create_preview(markdown)

            # Store the canonical HTML URL (strip .md) for compatibility
            html_url = md_url.removesuffix(".md")

            pages.append(PageData(
                url=html_url,
                title=title,
                section=section,
                language=language,
                content=markdown,
                content_preview=preview,
            ))
            logger.info(f"Indexed: {title}")

    logger.info(f"Indexed {len(pages)} pages for rev")
    return {
        "vendor": "rev",
        "version": version,
        "built_at": datetime.now().isoformat(),
        "pages": [asdict(p) for p in pages],
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Build REV Robotics documentation index"
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

    print(f"\n✓ REV index saved to {output_path}")
    print(f"  Pages indexed: {len(index['pages'])}")


if __name__ == "__main__":
    asyncio.run(main())
