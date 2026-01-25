"""HTML cleaning and text extraction utilities."""

import re
from typing import Optional

from bs4 import BeautifulSoup, NavigableString, Tag


# Language detection patterns for code blocks
LANGUAGE_INDICATORS = {
    "java": [
        r"import\s+(?:com\.|edu\.|org\.|java\.)",
        r"public\s+class\s+\w+",
        r"(?:public|private|protected)\s+(?:static\s+)?(?:void|int|String|boolean)",
        r"System\.out\.println",
        r"@Override",
        r"new\s+\w+\(",
    ],
    "python": [
        r"^import\s+\w+",
        r"^from\s+\w+\s+import",
        r"def\s+\w+\s*\(",
        r"self\.",
        r"__init__",
        r"print\s*\(",
        r":\s*$",  # Colon at end of line
    ],
    "cpp": [
        r"#include\s*<",
        r"#include\s*\"",
        r"std::",
        r"frc::",
        r"rev::",
        r"ctre::",
        r"void\s+\w+::\w+",
        r"^\s*using\s+namespace",
        r"->\w+\(",  # Arrow operator
    ],
}


def detect_code_language(code_text: str, class_hints: list[str] = None) -> Optional[str]:
    """
    Detect programming language from code text and/or class hints.

    Args:
        code_text: The actual code content
        class_hints: CSS classes from the code element

    Returns:
        Detected language or None
    """
    # Check class hints first (more reliable)
    if class_hints:
        class_str = " ".join(class_hints).lower()
        for lang in ["java", "python", "py", "cpp", "c++"]:
            if lang in class_str:
                return "python" if lang == "py" else ("cpp" if lang == "c++" else lang)

        # Check for highlight.js / prism patterns
        for cls in class_hints:
            cls_lower = cls.lower()
            if cls_lower.startswith("language-"):
                lang = cls_lower.replace("language-", "")
                if lang in ("java", "python", "py", "cpp", "c++", "cxx"):
                    return "python" if lang == "py" else ("cpp" if lang in ("c++", "cxx") else lang)
            if cls_lower.startswith("highlight-"):
                lang = cls_lower.replace("highlight-", "")
                if lang in ("java", "python", "cpp"):
                    return lang

    # Fall back to content analysis
    if not code_text or len(code_text) < 10:
        return None

    scores = {"java": 0, "python": 0, "cpp": 0}

    for lang, patterns in LANGUAGE_INDICATORS.items():
        for pattern in patterns:
            if re.search(pattern, code_text, re.MULTILINE):
                scores[lang] += 1

    # Need at least 2 matches to be confident
    max_lang = max(scores, key=scores.get)
    if scores[max_lang] >= 2:
        return max_lang

    return None


class HtmlCleaner:
    """Extract and clean text content from HTML documentation pages."""
    
    # Tags to completely remove (including content)
    REMOVE_TAGS = {
        "script", "style", "nav", "header", "footer", "aside",
        "form", "button", "input", "select", "textarea",
        "iframe", "noscript", "svg", "canvas", "video", "audio"
    }
    
    # Tags that typically contain navigation/boilerplate
    BOILERPLATE_CLASSES = {
        "nav", "navigation", "navbar", "sidebar", "menu",
        "footer", "header", "breadcrumb", "toc", "table-of-contents",
        "edit-page", "page-nav", "pagination", "social", "share",
        "advertisement", "ad", "banner", "cookie"
    }
    
    # Tags that indicate main content areas
    CONTENT_SELECTORS = [
        "main",
        "article",
        "[role='main']",
        ".main-content",
        ".content",
        ".documentation",
        ".doc-content",
        "#content",
        "#main-content"
    ]
    
    def __init__(self, parser: str = "lxml"):
        """
        Initialize the HTML cleaner.
        
        Args:
            parser: BeautifulSoup parser to use (default: lxml for speed)
        """
        self.parser = parser
    
    def extract_content(self, html: str, url: Optional[str] = None) -> str:
        """
        Extract main content from HTML, removing boilerplate.
        
        Args:
            html: Raw HTML string
            url: Optional URL for context-specific cleaning
            
        Returns:
            Cleaned text content
        """
        soup = BeautifulSoup(html, self.parser)
        
        # Remove unwanted tags completely
        for tag_name in self.REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        # Remove elements with boilerplate classes
        for class_pattern in self.BOILERPLATE_CLASSES:
            for element in soup.find_all(class_=re.compile(class_pattern, re.I)):
                element.decompose()
        
        # Try to find main content area
        content = self._find_main_content(soup)
        if content is None:
            content = soup.body if soup.body else soup
        
        # Extract and clean text
        text = self._extract_text(content)
        text = self._normalize_whitespace(text)
        
        return text
    
    def _find_main_content(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the main content area using various selectors."""
        for selector in self.CONTENT_SELECTORS:
            try:
                element = soup.select_one(selector)
                if element and len(element.get_text(strip=True)) > 100:
                    return element
            except Exception:
                continue
        return None
    
    def _extract_text(self, element: Tag) -> str:
        """
        Extract text from an element, preserving structure.
        
        Handles code blocks, lists, and headings specially.
        """
        parts = []
        
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    parts.append(text)
            elif isinstance(child, Tag):
                if child.name in self.REMOVE_TAGS:
                    continue
                
                # Handle specific elements
                if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    heading_text = child.get_text(strip=True)
                    if heading_text:
                        parts.append(f"\n\n## {heading_text}\n")
                
                elif child.name == "pre":
                    # Code block - preserve formatting and detect language
                    code_text = child.get_text()
                    if code_text.strip():
                        # Get language from class hints
                        code_elem = child.find("code") or child
                        class_hints = code_elem.get("class", [])
                        if isinstance(class_hints, str):
                            class_hints = class_hints.split()

                        # Also check parent pre element classes
                        pre_classes = child.get("class", [])
                        if isinstance(pre_classes, str):
                            pre_classes = pre_classes.split()
                        all_hints = class_hints + pre_classes

                        lang = detect_code_language(code_text, all_hints)
                        lang_tag = lang if lang else ""
                        parts.append(f"\n```{lang_tag}\n{code_text}\n```\n")
                
                elif child.name == "code" and child.parent.name != "pre":
                    # Inline code
                    parts.append(f"`{child.get_text()}`")
                
                elif child.name in ("ul", "ol"):
                    # Lists
                    list_text = self._extract_list(child)
                    if list_text:
                        parts.append(f"\n{list_text}\n")
                
                elif child.name == "p":
                    p_text = child.get_text(strip=True)
                    if p_text:
                        parts.append(f"\n{p_text}\n")
                
                elif child.name in ("table",):
                    table_text = self._extract_table(child)
                    if table_text:
                        parts.append(f"\n{table_text}\n")
                
                elif child.name in ("div", "section", "article"):
                    # Recurse into container elements
                    nested = self._extract_text(child)
                    if nested.strip():
                        parts.append(nested)
                
                else:
                    # Other elements - just get text
                    text = child.get_text(strip=True)
                    if text:
                        parts.append(text)
        
        return " ".join(parts)
    
    def _extract_list(self, list_element: Tag) -> str:
        """Extract text from a list element."""
        items = []
        for i, li in enumerate(list_element.find_all("li", recursive=False)):
            text = li.get_text(strip=True)
            if text:
                prefix = "-" if list_element.name == "ul" else f"{i + 1}."
                items.append(f"  {prefix} {text}")
        return "\n".join(items)
    
    def _extract_table(self, table: Tag) -> str:
        """Extract text from a table, simplified format."""
        rows = []
        for tr in table.find_all("tr"):
            cells = []
            for cell in tr.find_all(["th", "td"]):
                cells.append(cell.get_text(strip=True))
            if cells:
                rows.append(" | ".join(cells))
        return "\n".join(rows)
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in extracted text."""
        # Replace multiple spaces with single space
        text = re.sub(r"[ \t]+", " ", text)
        # Replace more than 2 newlines with 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Strip leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
        # Final strip
        return text.strip()
    
    def extract_title(self, html: str) -> Optional[str]:
        """Extract the page title from HTML."""
        soup = BeautifulSoup(html, self.parser)
        
        # Try <title> tag first
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # Clean up common suffixes
            for sep in [" — ", " - ", " | ", " · "]:
                if sep in title:
                    title = title.split(sep)[0].strip()
            return title
        
        # Try h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        
        return None
    
    def extract_meta_description(self, html: str) -> Optional[str]:
        """Extract meta description from HTML."""
        soup = BeautifulSoup(html, self.parser)
        
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"].strip()
        
        # Try OpenGraph description
        og_meta = soup.find("meta", attrs={"property": "og:description"})
        if og_meta and og_meta.get("content"):
            return og_meta["content"].strip()
        
        return None
    
    def create_preview(self, text: str, max_length: int = 300) -> str:
        """
        Create a preview/snippet from full text content.
        
        Args:
            text: Full text content
            max_length: Maximum preview length
            
        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= max_length:
            return text
        
        # Try to break at a sentence boundary
        truncated = text[:max_length]
        
        # Look for last sentence end
        for sep in [". ", ".\n", "! ", "? "]:
            last_sep = truncated.rfind(sep)
            if last_sep > max_length * 0.5:
                return truncated[:last_sep + 1].strip()
        
        # Fall back to word boundary
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.7:
            return truncated[:last_space].strip() + "..."
        
        return truncated.strip() + "..."




