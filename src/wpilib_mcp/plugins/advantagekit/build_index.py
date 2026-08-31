#!/usr/bin/env python3
"""
Build documentation index for AdvantageKit.

Uses the known sitemap URL list. Attempts to fetch raw Markdown from the
Mechanical-Advantage/AdvantageKit GitHub repo first; falls back to HTML.

Usage:
    python -m wpilib_mcp.plugins.advantagekit.build_index

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
from typing import Optional

import httpx
from bs4 import BeautifulSoup

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

BASE_URL = "https://docs.advantagekit.org"
GITHUB_RAW = "https://raw.githubusercontent.com/Mechanical-Advantage/AdvantageKit/main/docs/docs"
RATE_LIMIT = 0.3

# Content pages from sitemap — category index pages and /search excluded
SITEMAP_URLS = [
    "https://docs.advantagekit.org/getting-started/what-is-advantagekit/",
    "https://docs.advantagekit.org/getting-started/what-is-advantagekit/champs-conference",
    "https://docs.advantagekit.org/getting-started/what-is-advantagekit/example-bug-fixes",
    "https://docs.advantagekit.org/getting-started/what-is-advantagekit/example-output-logging",
    "https://docs.advantagekit.org/getting-started/what-is-advantagekit/example-rapid-iteration",
    "https://docs.advantagekit.org/getting-started/installation/",
    "https://docs.advantagekit.org/getting-started/installation/existing-projects",
    "https://docs.advantagekit.org/getting-started/installation/version-control",
    "https://docs.advantagekit.org/getting-started/installation/vscode-welcome",
    "https://docs.advantagekit.org/getting-started/template-projects",
    "https://docs.advantagekit.org/getting-started/template-projects/diff-drive-template",
    "https://docs.advantagekit.org/getting-started/template-projects/kitbot-template",
    "https://docs.advantagekit.org/getting-started/template-projects/skeleton-template",
    "https://docs.advantagekit.org/getting-started/template-projects/spark-swerve-template",
    "https://docs.advantagekit.org/getting-started/template-projects/talonfx-swerve-template",
    "https://docs.advantagekit.org/getting-started/template-projects/vision-template",
    "https://docs.advantagekit.org/getting-started/traditional-replay",
    "https://docs.advantagekit.org/getting-started/replay-watch",
    "https://docs.advantagekit.org/getting-started/common-issues",
    "https://docs.advantagekit.org/getting-started/common-issues/multithreading",
    "https://docs.advantagekit.org/getting-started/common-issues/non-deterministic-data-sources",
    "https://docs.advantagekit.org/getting-started/common-issues/uninitialized-inputs",
    "https://docs.advantagekit.org/data-flow/supported-types",
    "https://docs.advantagekit.org/data-flow/built-in-logging",
    "https://docs.advantagekit.org/data-flow/recording-inputs",
    "https://docs.advantagekit.org/data-flow/recording-inputs/io-interfaces",
    "https://docs.advantagekit.org/data-flow/recording-inputs/annotation-logging",
    "https://docs.advantagekit.org/data-flow/recording-inputs/dashboard-inputs",
    "https://docs.advantagekit.org/data-flow/recording-outputs/",
    "https://docs.advantagekit.org/data-flow/recording-outputs/annotation-logging",
    "https://docs.advantagekit.org/data-flow/sysid-compatibility",
    "https://docs.advantagekit.org/theory/log-replay-comparison",
    "https://docs.advantagekit.org/theory/deterministic-timestamps",
    "https://docs.advantagekit.org/theory/high-frequency-odometry",
    "https://docs.advantagekit.org/theory/case-studies",
    "https://docs.advantagekit.org/theory/case-studies/aiming-functions",
    "https://docs.advantagekit.org/theory/case-studies/apriltag-tuning",
    "https://docs.advantagekit.org/theory/case-studies/autoscoring",
    "https://docs.advantagekit.org/theory/case-studies/command-gremlins",
    "https://docs.advantagekit.org/theory/case-studies/elevator-profile",
    "https://docs.advantagekit.org/theory/case-studies/retroreflective-tuning",
    "https://docs.advantagekit.org/whats-new",
]


def extract_section(url: str) -> str:
    u = url.lower()
    if "/getting-started/installation" in u:
        return "Installation"
    elif "/getting-started/template-projects" in u:
        return "Template Projects"
    elif "/getting-started/common-issues" in u:
        return "Common Issues"
    elif "/getting-started/" in u:
        return "Getting Started"
    elif "/data-flow/recording-inputs" in u:
        return "Recording Inputs"
    elif "/data-flow/recording-outputs" in u:
        return "Recording Outputs"
    elif "/data-flow/" in u:
        return "Data Flow"
    elif "/theory/case-studies" in u:
        return "Case Studies"
    elif "/theory/" in u:
        return "Theory"
    elif "/whats-new" in u:
        return "What's New"
    return "General"


def to_github_raw_url(doc_url: str) -> Optional[str]:
    """Convert docs.advantagekit.org URL to a GitHub raw markdown candidate URL."""
    prefix = "https://docs.advantagekit.org/"
    if not doc_url.startswith(prefix):
        return None
    path = doc_url[len(prefix):].rstrip("/")
    if not path:
        return None
    # Trailing-slash URLs are directory index pages
    if doc_url.endswith("/"):
        return f"{GITHUB_RAW}/{path}/index.md"
    return f"{GITHUB_RAW}/{path}.md"


def extract_docusaurus_content(soup: BeautifulSoup) -> str:
    """Extract main content from a Docusaurus HTML page."""
    for selector in [
        "nav", "header", "footer", ".navbar", ".sidebar",
        ".theme-doc-toc-desktop", ".pagination-nav",
        ".theme-doc-breadcrumbs", "script", "style",
    ]:
        for elem in soup.select(selector):
            elem.decompose()

    main = (
        soup.find("article") or
        soup.find("main") or
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
        headers={"User-Agent": "FIRST-Agentic-CSA-advantagekit-Indexer/1.0"}
    ) as client:
        for url in SITEMAP_URLS:
            await asyncio.sleep(RATE_LIMIT)

            content = None
            title = None
            language = "Java"

            # Try GitHub raw markdown first
            gh_url = to_github_raw_url(url)
            if gh_url:
                try:
                    resp = await client.get(gh_url)
                    resp.raise_for_status()
                    markdown = resp.text
                    if len(markdown.strip()) >= 100:
                        title = extract_md_title(markdown)
                        language = detect_md_language(markdown) or "Java"
                        content = markdown
                        logger.debug(f"Got markdown from GitHub: {gh_url}")
                except Exception:
                    pass

            # Fall back to HTML
            if not content:
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "lxml")
                    content = extract_docusaurus_content(soup)
                    if not title:
                        h1 = soup.find("h1")
                        if h1:
                            title = h1.get_text(strip=True)
                        elif soup.title:
                            t = soup.title.string or ""
                            for sep in [" | ", " - ", " — ", " · "]:
                                if sep in t:
                                    title = t.split(sep)[0].strip()
                                    break
                            else:
                                title = t.strip()
                except Exception as e:
                    logger.warning(f"Failed to fetch {url}: {e}")
                    continue

            if not content or len(content) < 50:
                logger.warning(f"Skipping short/empty page: {url}")
                continue

            if not title:
                title = url.rstrip("/").split("/")[-1].replace("-", " ").title()

            section = extract_section(url)
            pages.append(PageData(
                url=url,
                title=title,
                section=section,
                language=language,
                content=content,
                content_preview=create_preview(content),
            ))
            logger.info(f"Indexed: {title}")

    logger.info(f"Indexed {len(pages)} pages for advantagekit")
    return {
        "vendor": "advantagekit",
        "version": version,
        "built_at": datetime.now().isoformat(),
        "pages": [asdict(p) for p in pages],
    }


async def main():
    parser = argparse.ArgumentParser(description="Build AdvantageKit documentation index")
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

    print(f"\n✓ AdvantageKit index saved to {output_path}")
    print(f"  Pages indexed: {len(index['pages'])}")


if __name__ == "__main__":
    asyncio.run(main())
