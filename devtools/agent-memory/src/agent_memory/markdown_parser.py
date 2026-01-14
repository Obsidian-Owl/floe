"""Markdown parser for extracting content and metadata from documentation files.

Parses markdown files with optional YAML frontmatter, extracting structured content
for indexing in the Cognee knowledge graph.

Usage:
    >>> from pathlib import Path
    >>> from agent_memory.markdown_parser import parse_markdown_file
    >>> parsed = parse_markdown_file(Path("docs/architecture/README.md"))
    >>> parsed.title
    'Architecture Overview'
    >>> parsed.metadata
    {'tags': ['architecture', 'overview']}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ParsedContent:
    """Parsed markdown content with extracted metadata.

    Attributes:
        title: Document title (from frontmatter or first H1 heading).
        content: Full markdown content (excluding frontmatter).
        metadata: YAML frontmatter as dictionary.
        source_path: Original file path.
        headers: List of header texts extracted from the document.
    """

    title: str
    content: str
    metadata: dict[str, Any]
    source_path: Path
    headers: list[str] = field(default_factory=list)


# Regex patterns for parsing
FRONTMATTER_PATTERN = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n?",
    re.DOTALL,
)
"""Matches YAML frontmatter between --- delimiters."""

H1_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
"""Matches first-level headings (# Title)."""

HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
"""Matches all heading levels (# through ######)."""


def _extract_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter from markdown content.

    Args:
        content: Raw markdown content.

    Returns:
        Tuple of (metadata dict, remaining content without frontmatter).
    """
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}, content

    frontmatter_text = match.group(1)
    remaining_content = content[match.end() :]

    try:
        loaded = yaml.safe_load(frontmatter_text)
        if loaded is None or not isinstance(loaded, dict):
            metadata: dict[str, Any] = {}
        else:
            # Cast to proper type since yaml.safe_load returns Any
            metadata = {str(k): v for k, v in loaded.items()}
    except yaml.YAMLError:
        # Invalid YAML, treat as no frontmatter
        metadata = {}

    return metadata, remaining_content


def _extract_title(content: str, metadata: dict[str, Any]) -> str:
    """Extract document title from metadata or first H1 heading.

    Priority:
    1. 'title' field in frontmatter metadata
    2. First H1 heading in content
    3. Empty string if no title found

    Args:
        content: Markdown content (without frontmatter).
        metadata: Parsed frontmatter metadata.

    Returns:
        Document title string.
    """
    # Check frontmatter for title
    if "title" in metadata:
        return str(metadata["title"])

    # Find first H1 heading
    match = H1_PATTERN.search(content)
    if match:
        return match.group(1).strip()

    return ""


def _extract_headers(content: str) -> list[str]:
    """Extract all headers from markdown content.

    Args:
        content: Markdown content.

    Returns:
        List of header text strings (without # prefix).
    """
    headers: list[str] = []
    for match in HEADER_PATTERN.finditer(content):
        header_text = match.group(2).strip()
        headers.append(header_text)
    return headers


def parse_markdown_file(path: Path) -> ParsedContent:
    """Parse a markdown file and extract structured content.

    Reads the file, extracts YAML frontmatter if present, identifies the title
    (from frontmatter or first H1), and extracts all headers for structural
    understanding.

    Args:
        path: Path to the markdown file.

    Returns:
        ParsedContent with title, content, metadata, source_path, and headers.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If the file cannot be read.

    Examples:
        >>> # File with frontmatter:
        >>> # ---
        >>> # title: My Document
        >>> # tags: [doc, example]
        >>> # ---
        >>> # # Heading
        >>> # Content here.
        >>> parsed = parse_markdown_file(Path("doc.md"))
        >>> parsed.title
        'My Document'
        >>> parsed.metadata['tags']
        ['doc', 'example']
    """
    raw_content = path.read_text(encoding="utf-8")

    metadata, content = _extract_frontmatter(raw_content)
    title = _extract_title(content, metadata)
    headers = _extract_headers(content)

    return ParsedContent(
        title=title,
        content=content,
        metadata=metadata,
        source_path=path,
        headers=headers,
    )


def parse_markdown_string(content: str, source_path: Path | None = None) -> ParsedContent:
    """Parse markdown content from a string.

    Useful for testing or when content is already in memory.

    Args:
        content: Raw markdown content string.
        source_path: Optional path to associate with the content.

    Returns:
        ParsedContent with extracted data.

    Examples:
        >>> content = '''---
        ... title: Test
        ... ---
        ... # Heading
        ... Body text.
        ... '''
        >>> parsed = parse_markdown_string(content)
        >>> parsed.title
        'Test'
    """
    metadata, body = _extract_frontmatter(content)
    title = _extract_title(body, metadata)
    headers = _extract_headers(body)

    return ParsedContent(
        title=title,
        content=body,
        metadata=metadata,
        source_path=source_path or Path("<string>"),
        headers=headers,
    )
