"""Unit tests for markdown_parser module.

Tests markdown parsing with YAML frontmatter extraction.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from agent_memory.markdown_parser import (
    ParsedContent,
    parse_markdown_file,
    parse_markdown_string,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def sample_markdown_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary markdown file with frontmatter."""
    content = """---
title: Test Document
tags:
  - test
  - example
author: Test Author
---

# Main Heading

This is the body content.

## Section One

Content for section one.

### Subsection

More details here.
"""
    file_path = tmp_path / "test.md"
    file_path.write_text(content)
    yield file_path


@pytest.fixture
def markdown_without_frontmatter(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a markdown file without frontmatter."""
    content = """# Document Title

This is content without frontmatter.

## Another Section

More content.
"""
    file_path = tmp_path / "no_frontmatter.md"
    file_path.write_text(content)
    yield file_path


class TestParsedContent:
    """Tests for ParsedContent dataclass."""

    def test_parsed_content_is_frozen(self) -> None:
        """Test that ParsedContent is immutable."""
        parsed = ParsedContent(
            title="Test",
            content="Body",
            metadata={},
            source_path=Path("test.md"),
            headers=[],
        )
        with pytest.raises(AttributeError):
            parsed.title = "New Title"  # type: ignore[misc]


class TestParseMarkdownFile:
    """Tests for parse_markdown_file function."""

    @pytest.mark.requirement("FR-004")
    def test_parse_file_with_frontmatter(self, sample_markdown_file: Path) -> None:
        """Test parsing file with YAML frontmatter."""
        result = parse_markdown_file(sample_markdown_file)

        assert result.title == "Test Document"
        assert result.metadata["tags"] == ["test", "example"]
        assert result.metadata["author"] == "Test Author"
        assert result.source_path == sample_markdown_file

    @pytest.mark.requirement("FR-004")
    def test_parse_file_without_frontmatter(
        self, markdown_without_frontmatter: Path
    ) -> None:
        """Test parsing file without frontmatter uses H1 as title."""
        result = parse_markdown_file(markdown_without_frontmatter)

        assert result.title == "Document Title"
        assert result.metadata == {}
        assert "# Document Title" in result.content

    @pytest.mark.requirement("FR-004")
    def test_extracts_all_headers(self, sample_markdown_file: Path) -> None:
        """Test that all headers are extracted."""
        result = parse_markdown_file(sample_markdown_file)

        assert "Main Heading" in result.headers
        assert "Section One" in result.headers
        assert "Subsection" in result.headers

    def test_file_not_found_raises_error(self) -> None:
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_markdown_file(Path("/nonexistent/file.md"))


class TestParseMarkdownString:
    """Tests for parse_markdown_string function."""

    @pytest.mark.requirement("FR-004")
    def test_parse_string_with_frontmatter(self) -> None:
        """Test parsing string content with frontmatter."""
        content = """---
title: String Test
version: 1.0
---

# Content Heading

Body text here.
"""
        result = parse_markdown_string(content)

        assert result.title == "String Test"
        assert result.metadata["version"] == 1.0
        assert "Body text here." in result.content

    @pytest.mark.requirement("FR-004")
    def test_parse_string_title_from_h1(self) -> None:
        """Test title extraction from H1 when no frontmatter title."""
        content = """---
author: Someone
---

# The Real Title

Content.
"""
        result = parse_markdown_string(content)

        assert result.title == "The Real Title"
        assert result.metadata["author"] == "Someone"

    def test_parse_string_empty_frontmatter(self) -> None:
        """Test parsing with empty frontmatter."""
        content = """---
---

# Just a Heading

Content.
"""
        result = parse_markdown_string(content)

        assert result.title == "Just a Heading"
        assert result.metadata == {}

    def test_parse_string_invalid_yaml(self) -> None:
        """Test parsing with malformed YAML frontmatter."""
        content = """---
title: [invalid yaml
  - not closed
---

# Fallback Title

Content.
"""
        result = parse_markdown_string(content)

        # Should fall back to H1 since YAML is invalid
        assert result.title == "Fallback Title"
        assert result.metadata == {}

    def test_parse_string_no_title(self) -> None:
        """Test parsing when no title can be found."""
        content = """Just some content without any heading or frontmatter."""

        result = parse_markdown_string(content)

        assert result.title == ""
        assert result.content == content

    def test_source_path_default(self) -> None:
        """Test default source_path for string parsing."""
        result = parse_markdown_string("# Test")

        assert result.source_path == Path("<string>")

    def test_source_path_custom(self) -> None:
        """Test custom source_path for string parsing."""
        custom_path = Path("/custom/path.md")
        result = parse_markdown_string("# Test", source_path=custom_path)

        assert result.source_path == custom_path


class TestFrontmatterEdgeCases:
    """Tests for edge cases in frontmatter handling."""

    def test_non_dict_frontmatter(self) -> None:
        """Test handling of non-dict YAML frontmatter."""
        content = """---
- list
- item
---

# Title

Content.
"""
        result = parse_markdown_string(content)

        # Non-dict should be treated as empty metadata
        assert result.metadata == {}
        assert result.title == "Title"

    def test_frontmatter_with_complex_values(self) -> None:
        """Test frontmatter with nested structures."""
        content = """---
title: Complex Doc
nested:
  key1: value1
  key2:
    - item1
    - item2
---

Content.
"""
        result = parse_markdown_string(content)

        assert result.metadata["nested"]["key1"] == "value1"
        assert result.metadata["nested"]["key2"] == ["item1", "item2"]

    def test_content_preserved_after_frontmatter(self) -> None:
        """Test that content after frontmatter is fully preserved."""
        content = """---
title: Test
---
First line after frontmatter.

Second paragraph.
"""
        result = parse_markdown_string(content)

        assert "First line after frontmatter." in result.content
        assert "Second paragraph." in result.content
        # Frontmatter should not be in content
        assert "---" not in result.content
