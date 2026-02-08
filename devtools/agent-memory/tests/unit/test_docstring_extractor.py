"""Unit tests for docstring_extractor module.

Tests Python docstring extraction using AST parsing with Google-style format support.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from agent_memory.docstring_extractor import DocstringEntry, extract_docstrings

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def python_file_with_class(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary Python file with a class definition."""
    content = '''"""Module docstring."""

class MyClass:
    """A sample class for testing.

    This class demonstrates docstring extraction with multiple sections.

    Attributes:
        name: The name of the instance.
        value: A numeric value.
    """

    def __init__(self, name: str, value: int = 0) -> None:
        """Initialize the class.

        Args:
            name: The name to use.
            value: Optional initial value.
        """
        self.name = name
        self.value = value
'''
    file_path = tmp_path / "sample_class.py"
    file_path.write_text(content)
    yield file_path


@pytest.fixture
def python_file_with_function(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary Python file with a function definition."""
    content = '''"""Module with functions."""

def calculate_total(items: list[int], multiplier: float = 1.0) -> float:
    """Calculate the total of items with an optional multiplier.

    Args:
        items: List of integer values to sum.
        multiplier: Factor to multiply the sum by.

    Returns:
        The total as a float value.

    Raises:
        ValueError: If items is empty.
        TypeError: If items contains non-integers.

    Examples:
        >>> calculate_total([1, 2, 3])
        6.0
        >>> calculate_total([1, 2, 3], multiplier=2.0)
        12.0
    """
    if not items:
        raise ValueError("items cannot be empty")
    return sum(items) * multiplier
'''
    file_path = tmp_path / "sample_function.py"
    file_path.write_text(content)
    yield file_path


@pytest.fixture
def python_file_with_malformed_docstring(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary Python file with malformed docstrings."""
    content = '''"""Module docstring."""

def no_docstring():
    pass

def empty_docstring():
    """"""
    pass

def incomplete_sections():
    """A function with incomplete sections.

    Args:
        This is not properly formatted
    Returns
        Missing colon
    """
    pass

class NoDocstringClass:
    pass
'''
    file_path = tmp_path / "malformed.py"
    file_path.write_text(content)
    yield file_path


@pytest.fixture
def python_file_with_syntax_error(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary Python file with syntax errors."""
    content = '''"""Module with syntax error."""

def broken_function(
    # Missing closing parenthesis
'''
    file_path = tmp_path / "syntax_error.py"
    file_path.write_text(content)
    yield file_path


class TestDocstringEntry:
    """Tests for DocstringEntry model."""

    def test_docstring_entry_is_frozen(self) -> None:
        """Test that DocstringEntry is immutable."""
        entry = DocstringEntry(
            name="test_func",
            entry_type="function",
            docstring="Test docstring.",
            source_path=Path("test.py"),
            line_number=1,
        )
        with pytest.raises(AttributeError):
            entry.name = "new_name"  # type: ignore[misc]

    def test_docstring_entry_fields(self) -> None:
        """Test DocstringEntry contains all required fields."""
        entry = DocstringEntry(
            name="MyClass",
            entry_type="class",
            docstring="Class docstring.",
            source_path=Path("module.py"),
            line_number=10,
            bases=["BaseClass"],
            methods=["__init__", "process"],
        )
        assert entry.name == "MyClass"
        assert entry.entry_type == "class"
        assert entry.docstring == "Class docstring."
        assert entry.source_path == Path("module.py")
        assert entry.line_number == 10
        assert entry.bases == ["BaseClass"]
        assert entry.methods == ["__init__", "process"]


class TestExtractClassDocstring:
    """Tests for class docstring extraction."""

    @pytest.mark.requirement("FR-007")
    def test_extract_class_docstring(self, python_file_with_class: Path) -> None:
        """Test extraction of class docstring with name and line number."""
        entries = extract_docstrings(python_file_with_class)

        # Find the class entry
        class_entries = [e for e in entries if e.entry_type == "class"]
        assert len(class_entries) == 1

        class_entry = class_entries[0]
        assert class_entry.name == "MyClass"
        assert "A sample class for testing" in class_entry.docstring
        assert class_entry.line_number == 3  # class MyClass: is on line 3 (after module docstring)
        assert class_entry.source_path == python_file_with_class

    @pytest.mark.requirement("FR-007")
    def test_extract_class_with_bases(self, tmp_path: Path) -> None:
        """Test extraction of class docstring includes base classes."""
        content = '''"""Module."""

class ChildClass(ParentClass, MixinClass):
    """A child class with inheritance."""
    pass
'''
        file_path = tmp_path / "inheritance.py"
        file_path.write_text(content)

        entries = extract_docstrings(file_path)
        class_entries = [e for e in entries if e.entry_type == "class"]
        assert len(class_entries) == 1

        class_entry = class_entries[0]
        assert class_entry.name == "ChildClass"
        assert "ParentClass" in class_entry.bases
        assert "MixinClass" in class_entry.bases

    @pytest.mark.requirement("FR-007")
    def test_extract_class_methods(self, python_file_with_class: Path) -> None:
        """Test extraction captures method names for classes."""
        entries = extract_docstrings(python_file_with_class)

        class_entries = [e for e in entries if e.entry_type == "class"]
        assert len(class_entries) == 1

        class_entry = class_entries[0]
        assert "__init__" in class_entry.methods


class TestExtractMethodDocstring:
    """Tests for method/function docstring extraction."""

    @pytest.mark.requirement("FR-006")
    def test_extract_function_docstring(self, python_file_with_function: Path) -> None:
        """Test extraction of standalone function docstring."""
        entries = extract_docstrings(python_file_with_function)

        # Find function entries
        func_entries = [e for e in entries if e.entry_type == "function"]
        assert len(func_entries) == 1

        func_entry = func_entries[0]
        assert func_entry.name == "calculate_total"
        assert "Calculate the total" in func_entry.docstring
        assert func_entry.line_number == 3  # function starts on line 3 (after module docstring)

    @pytest.mark.requirement("FR-006")
    def test_extract_method_docstring(self, python_file_with_class: Path) -> None:
        """Test extraction of class method docstring."""
        entries = extract_docstrings(python_file_with_class)

        # Find method entries (inside class)
        method_entries = [e for e in entries if e.entry_type == "method"]
        assert len(method_entries) == 1

        method_entry = method_entries[0]
        assert method_entry.name == "__init__"
        assert "Initialize the class" in method_entry.docstring

    @pytest.mark.requirement("FR-006")
    def test_extract_function_signature(self, python_file_with_function: Path) -> None:
        """Test that function signature is captured."""
        entries = extract_docstrings(python_file_with_function)

        func_entries = [e for e in entries if e.entry_type == "function"]
        func_entry = func_entries[0]

        # Signature should be available
        assert func_entry.signature is not None
        assert "items" in func_entry.signature
        assert "multiplier" in func_entry.signature


class TestExtractGoogleStyleDocstring:
    """Tests for Google-style docstring section parsing."""

    @pytest.mark.requirement("FR-006")
    def test_parse_args_section(self, python_file_with_function: Path) -> None:
        """Test parsing of Args section in Google-style docstring."""
        entries = extract_docstrings(python_file_with_function)

        func_entries = [e for e in entries if e.entry_type == "function"]
        func_entry = func_entries[0]

        assert func_entry.sections is not None
        args_section = func_entry.sections.get("Args")
        assert args_section is not None
        assert "items" in args_section
        assert "multiplier" in args_section

    @pytest.mark.requirement("FR-006")
    def test_parse_returns_section(self, python_file_with_function: Path) -> None:
        """Test parsing of Returns section in Google-style docstring."""
        entries = extract_docstrings(python_file_with_function)

        func_entries = [e for e in entries if e.entry_type == "function"]
        func_entry = func_entries[0]

        assert func_entry.sections is not None
        returns_section = func_entry.sections.get("Returns")
        assert returns_section is not None
        assert "float" in returns_section.lower()

    @pytest.mark.requirement("FR-006")
    def test_parse_raises_section(self, python_file_with_function: Path) -> None:
        """Test parsing of Raises section in Google-style docstring."""
        entries = extract_docstrings(python_file_with_function)

        func_entries = [e for e in entries if e.entry_type == "function"]
        func_entry = func_entries[0]

        assert func_entry.sections is not None
        raises_section = func_entry.sections.get("Raises")
        assert raises_section is not None
        assert "ValueError" in raises_section
        assert "TypeError" in raises_section

    @pytest.mark.requirement("FR-006")
    def test_parse_examples_section(self, python_file_with_function: Path) -> None:
        """Test parsing of Examples section in Google-style docstring."""
        entries = extract_docstrings(python_file_with_function)

        func_entries = [e for e in entries if e.entry_type == "function"]
        func_entry = func_entries[0]

        assert func_entry.sections is not None
        examples_section = func_entry.sections.get("Examples")
        assert examples_section is not None
        assert "calculate_total" in examples_section
        assert "6.0" in examples_section

    @pytest.mark.requirement("FR-006")
    def test_parse_attributes_section(self, python_file_with_class: Path) -> None:
        """Test parsing of Attributes section in class docstring."""
        entries = extract_docstrings(python_file_with_class)

        class_entries = [e for e in entries if e.entry_type == "class"]
        class_entry = class_entries[0]

        assert class_entry.sections is not None
        attrs_section = class_entry.sections.get("Attributes")
        assert attrs_section is not None
        assert "name" in attrs_section
        assert "value" in attrs_section


class TestHandleMalformedDocstring:
    """Tests for handling malformed or missing docstrings."""

    @pytest.mark.requirement("FR-006")
    def test_function_without_docstring(self, python_file_with_malformed_docstring: Path) -> None:
        """Test handling of functions without docstrings."""
        entries = extract_docstrings(python_file_with_malformed_docstring)

        # Should not crash - functions without docstrings are skipped or have empty docstring
        func_names = [e.name for e in entries if e.entry_type == "function"]
        # no_docstring and empty_docstring should either be absent or have empty docstring
        assert "no_docstring" not in func_names or any(
            e.name == "no_docstring" and (e.docstring == "" or e.docstring is None) for e in entries
        )

    @pytest.mark.requirement("FR-006")
    def test_empty_docstring(self, python_file_with_malformed_docstring: Path) -> None:
        """Test handling of empty docstrings."""
        entries = extract_docstrings(python_file_with_malformed_docstring)

        # Find empty_docstring function
        empty_entries = [e for e in entries if e.name == "empty_docstring"]
        # Should either be absent or have empty docstring
        if empty_entries:
            assert empty_entries[0].docstring == "" or empty_entries[0].docstring is None

    @pytest.mark.requirement("FR-006")
    def test_incomplete_sections_graceful(self, python_file_with_malformed_docstring: Path) -> None:
        """Test graceful handling of incomplete Google-style sections."""
        entries = extract_docstrings(python_file_with_malformed_docstring)

        incomplete_entries = [e for e in entries if e.name == "incomplete_sections"]
        assert len(incomplete_entries) == 1

        # Should not crash - malformed sections handled gracefully
        entry = incomplete_entries[0]
        assert entry.docstring is not None
        # Sections should be either a dict (possibly empty) or None
        assert entry.sections is None or isinstance(entry.sections, dict)

    @pytest.mark.requirement("FR-006")
    def test_class_without_docstring(self, python_file_with_malformed_docstring: Path) -> None:
        """Test handling of classes without docstrings."""
        entries = extract_docstrings(python_file_with_malformed_docstring)

        # NoDocstringClass should either be absent or have empty docstring
        no_doc_class = [e for e in entries if e.name == "NoDocstringClass"]
        if no_doc_class:
            assert no_doc_class[0].docstring == "" or no_doc_class[0].docstring is None

    @pytest.mark.requirement("FR-006")
    def test_syntax_error_graceful(self, python_file_with_syntax_error: Path) -> None:
        """Test graceful handling of Python files with syntax errors."""
        # Should not raise exception, but return empty list or partial results
        entries = extract_docstrings(python_file_with_syntax_error)

        # Should return empty list or handle gracefully (not crash)
        assert isinstance(entries, list)


class TestExtractDocstringsEdgeCases:
    """Tests for edge cases in docstring extraction."""

    def test_nested_class(self, tmp_path: Path) -> None:
        """Test extraction of nested class docstrings."""
        content = '''"""Module."""

class Outer:
    """Outer class."""

    class Inner:
        """Inner class."""
        pass
'''
        file_path = tmp_path / "nested.py"
        file_path.write_text(content)

        entries = extract_docstrings(file_path)
        class_names = [e.name for e in entries if e.entry_type == "class"]

        assert "Outer" in class_names
        assert "Inner" in class_names

    def test_module_docstring(self, python_file_with_function: Path) -> None:
        """Test extraction of module-level docstring."""
        entries = extract_docstrings(python_file_with_function)

        module_entries = [e for e in entries if e.entry_type == "module"]
        assert len(module_entries) == 1
        assert "Module with functions" in module_entries[0].docstring

    def test_async_function(self, tmp_path: Path) -> None:
        """Test extraction of async function docstrings."""
        content = '''"""Module."""

async def fetch_data(url: str) -> dict:
    """Fetch data from URL.

    Args:
        url: The URL to fetch from.

    Returns:
        Response data as dictionary.
    """
    pass
'''
        file_path = tmp_path / "async_func.py"
        file_path.write_text(content)

        entries = extract_docstrings(file_path)
        func_entries = [e for e in entries if e.entry_type == "function"]

        assert len(func_entries) == 1
        assert func_entries[0].name == "fetch_data"
        assert "Fetch data from URL" in func_entries[0].docstring

    def test_decorated_function(self, tmp_path: Path) -> None:
        """Test extraction of decorated function docstrings."""
        content = '''"""Module."""

def decorator(func):
    return func

@decorator
@another_decorator
def decorated_func():
    """A decorated function."""
    pass
'''
        file_path = tmp_path / "decorated.py"
        file_path.write_text(content)

        entries = extract_docstrings(file_path)
        func_names = [e.name for e in entries if e.entry_type == "function"]

        assert "decorated_func" in func_names

    def test_file_not_found(self) -> None:
        """Test handling of non-existent file."""
        with pytest.raises(FileNotFoundError):
            extract_docstrings(Path("/nonexistent/file.py"))

    def test_non_python_file(self, tmp_path: Path) -> None:
        """Test handling of non-Python file content."""
        content = "This is not Python code"
        file_path = tmp_path / "not_python.py"
        file_path.write_text(content)

        # Should return empty list (no valid Python constructs)
        entries = extract_docstrings(file_path)
        assert isinstance(entries, list)
