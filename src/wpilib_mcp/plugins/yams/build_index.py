#!/usr/bin/env python3
"""
Build documentation index for YAMS (Yet Another Mechanism System).

Uses the known sitemap URL list and crawls each page's HTML content.

Usage:
    python -m wpilib_mcp.plugins.yams.build_index

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

try:
    from wpilib_mcp.utils.indexer import PageData
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from wpilib_mcp.utils.indexer import PageData


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = "https://yagsl.gitbook.io/yams"
RATE_LIMIT = 0.3

SITEMAP_URLS = [
    "https://yagsl.gitbook.io/yams",
    "https://yagsl.gitbook.io/yams/documentation",
    "https://yagsl.gitbook.io/yams/documentation/tutorials/arm",
    "https://yagsl.gitbook.io/yams/documentation/tutorials/elevator",
    "https://yagsl.gitbook.io/yams/documentation/tutorials/shooter-flywheels",
    "https://yagsl.gitbook.io/yams/documentation/tutorials/double-flywheel",
    "https://yagsl.gitbook.io/yams/documentation/tutorials/swerve-drive",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-to-set-an-arms-target-angle",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-to-set-an-elevators-target-height",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-to-run-sysid-on-a-arm",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-to-run-sysid-on-a-elevator",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-to-find-your-mechanism-circumference",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-to-shoot-with-a-shooter",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-do-i-control-a-mechanism-without-a-mechanism-class",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-do-i-sense-activity-based-off-of-the-current",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-do-i-use-a-dcmotor-that-isnt-in-wpilib",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-do-i-use-exponential-profiles",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-do-i-use-absolute-encoders-on-my-arm",
    "https://yagsl.gitbook.io/yams/documentation/how-to/how-to-disable-linear-closed-loop-control",
    "https://yagsl.gitbook.io/yams/documentation/details/advantagekit-integration",
    "https://yagsl.gitbook.io/yams/documentation/details/config-organization",
    "https://yagsl.gitbook.io/yams/documentation/details/editor",
    "https://yagsl.gitbook.io/yams/documentation/details/editor/feature-matrix",
    "https://yagsl.gitbook.io/yams/documentation/details/editor/simulation-only-pid-+-feedforward",
    "https://yagsl.gitbook.io/yams/documentation/details/editor/limiting-power-consumption",
    "https://yagsl.gitbook.io/yams/documentation/details/editor/exponential-profiles",
    "https://yagsl.gitbook.io/yams/documentation/details/editor/lqr-controllers",
    "https://yagsl.gitbook.io/yams/documentation/details/sensors",
    "https://yagsl.gitbook.io/yams/documentation/details/arms",
    "https://yagsl.gitbook.io/yams/documentation/details/elevators",
    "https://yagsl.gitbook.io/yams/documentation/details/turrets-wrists",
    "https://yagsl.gitbook.io/yams/documentation/details/shooters",
    "https://yagsl.gitbook.io/yams/documentation/details/run-vs-runto",
    "https://yagsl.gitbook.io/yams/documentation/details/setpoint-methods",
    "https://yagsl.gitbook.io/yams/documentation/details/interactive-blocks",
    "https://yagsl.gitbook.io/yams/documentation/details/integrations",
    "https://yagsl.gitbook.io/yams/documentation/details/sysid",
    "https://yagsl.gitbook.io/yams/documentation/details/easycrt",
    "https://yagsl.gitbook.io/yams/changelog",
]


def extract_section(url: str) -> str:
    u = url.lower()
    if "/documentation/tutorials/" in u:
        return "Tutorials"
    elif "/documentation/how-to/" in u:
        return "How To"
    elif "/documentation/details/editor" in u:
        return "Editor"
    elif "/documentation/details/" in u:
        return "Details"
    elif "/documentation" in u:
        return "Documentation"
    elif "/changelog" in u:
        return "Changelog"
    return "General"


def extract_gitbook_content(soup: BeautifulSoup) -> str:
    for selector in [
        "nav", "header", "footer", "[data-testid='sidebar']",
        ".gitbook-sidebar", ".sidebar", ".toc", ".page-nav",
        "script", "style", ".cookie-banner",
    ]:
        for elem in soup.select(selector):
            elem.decompose()

    main = (
        soup.find("main") or
        soup.find("div", class_=re.compile(r"content", re.I)) or
        soup.body
    )
    if main is None:
        return ""

    text = main.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


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


async def build(version: str = "latest") -> dict:
    pages: list[PageData] = []

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "FIRST-Agentic-CSA-yams-Indexer/1.0"}
    ) as client:
        for url in SITEMAP_URLS:
            await asyncio.sleep(RATE_LIMIT)
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            title = None
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
            if not title and soup.title:
                t = soup.title.string or ""
                for sep in [" | ", " - ", " — ", " · "]:
                    if sep in t:
                        title = t.split(sep)[0].strip()
                        break
                else:
                    title = t.strip()
            if not title:
                title = url.rstrip("/").split("/")[-1].replace("-", " ").title()

            content = extract_gitbook_content(soup)
            if len(content) < 50:
                logger.warning(f"Skipping short page: {url}")
                continue

            section = extract_section(url)
            pages.append(PageData(
                url=url,
                title=title,
                section=section,
                language="Java",
                content=content,
                content_preview=create_preview(content),
            ))
            logger.info(f"Indexed: {title}")

    logger.info(f"Indexed {len(pages)} pages for yams")
    return {
        "vendor": "yams",
        "version": version,
        "built_at": datetime.now().isoformat(),
        "pages": [asdict(p) for p in pages],
    }


async def main():
    parser = argparse.ArgumentParser(description="Build YAMS documentation index")
    parser.add_argument("--output", type=Path,
                        help="Output file path (default: data/index.json)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    data_dir = Path(__file__).parent / "data"
    output_path = args.output or (data_dir / "index.json")

    index = await build("latest")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\n✓ YAMS index saved to {output_path}")
    print(f"  Pages indexed: {len(index['pages'])}")


if __name__ == "__main__":
    asyncio.run(main())
