"""Shared utilities for extracting content from Markdown source files."""

import re
from typing import Optional


def extract_md_title(markdown: str) -> Optional[str]:
    """Return the first # heading as the page title."""
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return None


def detect_md_language(markdown: str) -> str:
    """Detect programming language from fenced code blocks in markdown."""
    has_java = bool(re.search(r"```java\b", markdown, re.I))
    has_cpp = bool(re.search(r"```(?:cpp|c\+\+)\b", markdown, re.I))
    has_python = bool(re.search(r"```python\b", markdown, re.I))
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
