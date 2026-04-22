#!/usr/bin/env python3
"""
Build documentation index for YAGSL (Yet Another Generic Swerve Library).

Uses the known sitemap URL list and crawls each page's HTML content.

Usage:
    python -m wpilib_mcp.plugins.yagsl.build_index

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

BASE_URL = "https://docs.yagsl.com"
RATE_LIMIT = 0.3

# All pages from sitemap, excluding the root (no useful standalone content)
SITEMAP_URLS = [
    "https://docs.yagsl.com/readme/resources",
    "https://docs.yagsl.com/overview/what-we-do",
    "https://docs.yagsl.com/overview/our-features",
    "https://docs.yagsl.com/overview/our-features/telemetry",
    "https://docs.yagsl.com/overview/our-features/simulation",
    "https://docs.yagsl.com/overview/our-features/lock-pose",
    "https://docs.yagsl.com/overview/our-features/max-speed",
    "https://docs.yagsl.com/overview/our-features/chassis-speed-discretization",
    "https://docs.yagsl.com/overview/our-features/vision-odometry",
    "https://docs.yagsl.com/overview/our-features/heading-correction",
    "https://docs.yagsl.com/overview/our-features/auto-centering-modules",
    "https://docs.yagsl.com/overview/our-features/offset-offloading",
    "https://docs.yagsl.com/overview/our-features/cosine-compensation",
    "https://docs.yagsl.com/overview/our-features/module-auto-synchronization",
    "https://docs.yagsl.com/overview/our-features/angular-velocity-compensation",
    "https://docs.yagsl.com/overview/changelog",
    "https://docs.yagsl.com/fundamentals/swerve-drive",
    "https://docs.yagsl.com/fundamentals/swerve-modules",
    "https://docs.yagsl.com/bringing-up-swerve/preface",
    "https://docs.yagsl.com/bringing-up-swerve/swerve-information",
    "https://docs.yagsl.com/bringing-up-swerve/check-your-gyroscope",
    "https://docs.yagsl.com/bringing-up-swerve/check-your-motors",
    "https://docs.yagsl.com/bringing-up-swerve/creating-your-first-configuration",
    "https://docs.yagsl.com/configuring-yagsl/getting-to-know-your-robot",
    "https://docs.yagsl.com/configuring-yagsl/dependency-installation",
    "https://docs.yagsl.com/configuring-yagsl/configuration",
    "https://docs.yagsl.com/configuring-yagsl/configuration/swerve-drive-configuration",
    "https://docs.yagsl.com/configuring-yagsl/configuration/physical-properties-configuration",
    "https://docs.yagsl.com/configuring-yagsl/configuration/pidf-properties-configuration",
    "https://docs.yagsl.com/configuring-yagsl/configuration/pidf-properties-configuration/pidf",
    "https://docs.yagsl.com/configuring-yagsl/configuration/swerve-module-configuration",
    "https://docs.yagsl.com/configuring-yagsl/configuration/controller-properties-configuration",
    "https://docs.yagsl.com/configuring-yagsl/configuration/device-configuration",
    "https://docs.yagsl.com/configuring-yagsl/code-setup",
    "https://docs.yagsl.com/configuring-yagsl/standard-conversion-factors",
    "https://docs.yagsl.com/configuring-yagsl/how-to-tune-pidf",
    "https://docs.yagsl.com/configuring-yagsl/when-to-invert",
    "https://docs.yagsl.com/configuring-yagsl/flowcharts",
    "https://docs.yagsl.com/configuring-yagsl/the-eight-steps",
    "https://docs.yagsl.com/configuring-yagsl/swerve-drive-drift",
    "https://docs.yagsl.com/configuring-yagsl/sparkmax-common-problems",
    "https://docs.yagsl.com/configuring-yagsl/verifying-your-module-locations",
    "https://docs.yagsl.com/configuring-yagsl/tuning-out-drift",
    "https://docs.yagsl.com/devices/gyroscope",
    "https://docs.yagsl.com/devices/gyroscope/navx",
    "https://docs.yagsl.com/devices/gyroscope/pigeon",
    "https://docs.yagsl.com/devices/gyroscope/pigeon-2.0",
    "https://docs.yagsl.com/devices/gyroscope/adxrs450",
    "https://docs.yagsl.com/devices/gyroscope/adis16448",
    "https://docs.yagsl.com/devices/gyroscope/adis16470",
    "https://docs.yagsl.com/devices/motor-controllers",
    "https://docs.yagsl.com/devices/motor-controllers/sparkmax",
    "https://docs.yagsl.com/devices/motor-controllers/sparkflex",
    "https://docs.yagsl.com/devices/motor-controllers/talonfx",
    "https://docs.yagsl.com/devices/absolute-encoders",
    "https://docs.yagsl.com/analytics-and-debugging/frc-web-components",
    "https://docs.yagsl.com/analytics-and-debugging/advantage-scope",
]


def extract_section(url: str) -> str:
    u = url.lower()
    if "/overview/our-features" in u:
        return "Features"
    elif "/overview/" in u:
        return "Overview"
    elif "/fundamentals/" in u:
        return "Fundamentals"
    elif "/bringing-up-swerve/" in u:
        return "Bringing Up Swerve"
    elif "/configuring-yagsl/configuration" in u:
        return "Configuration"
    elif "/configuring-yagsl/" in u:
        return "Configuring YAGSL"
    elif "/devices/gyroscope" in u:
        return "Gyroscopes"
    elif "/devices/motor-controllers" in u:
        return "Motor Controllers"
    elif "/devices/absolute-encoders" in u:
        return "Absolute Encoders"
    elif "/devices/" in u:
        return "Devices"
    elif "/analytics-and-debugging/" in u:
        return "Analytics & Debugging"
    return "General"


def extract_gitbook_content(soup: BeautifulSoup) -> str:
    """Extract main content from a GitBook HTML page."""
    # Remove navigation, sidebars, and chrome
    for selector in [
        "nav", "header", "footer", "[data-testid='sidebar']",
        ".gitbook-sidebar", ".sidebar", ".toc", ".page-nav",
        "script", "style", ".cookie-banner", ".intercom-app",
    ]:
        for elem in soup.select(selector):
            elem.decompose()

    # GitBook renders content in <main> or a content div
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
        headers={"User-Agent": "FIRST-Agentic-CSA-yagsl-Indexer/1.0"}
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

            # Extract title
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

    logger.info(f"Indexed {len(pages)} pages for yagsl")
    return {
        "vendor": "yagsl",
        "version": version,
        "built_at": datetime.now().isoformat(),
        "pages": [asdict(p) for p in pages],
    }


async def main():
    parser = argparse.ArgumentParser(description="Build YAGSL documentation index")
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

    print(f"\n✓ YAGSL index saved to {output_path}")
    print(f"  Pages indexed: {len(index['pages'])}")


if __name__ == "__main__":
    asyncio.run(main())
