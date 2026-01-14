"""Python docstring extractor using AST parsing.

Extracts docstrings from Python files with support for Google-style format sections.
Used to index Python codebase documentation into the Cognee knowledge graph.

Usage:
    >>> from pathlib import Path
    >>> from agent_memory.docstring_extractor import extract_docstrings
    >>> entries = extract_docstrings(Path("src/module.py"))
    >>> for entry in entries:
    ...     print(f"{entry.entry_type}: {entry.name}")
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class DocstringEntry:
    """Extracted docstring entry from a Python file.

    Attributes:
        name: Name of the module, class, function, or method.
        entry_type: Type of entry (module, class, function, method).
        docstring: The extracted docstring text.
        source_path: Path to the source file.
        line_number: Line number where the definition starts.
        bases: List of base class names (for classes only).
        methods: List of method names (for classes only).
        signature: Function/method signature string (for functions/methods).
        sections: Parsed Google-style sections (Args, Returns, Raises, Examples).
    """

    name: str
    entry_type: Literal["module", "class", "function", "method"]
    docstring: str
    source_path: Path
    line_number: int
    bases: list[str] = field(default_factory=lambda: [])  # noqa: RUF012
    methods: list[str] = field(default_factory=lambda: [])  # noqa: RUF012
    signature: str | None = None
    sections: dict[str, str] | None = None


# Google-style section headers
GOOGLE_STYLE_SECTIONS = frozenset({
    "Args",
    "Arguments",
    "Attributes",
    "Example",
    "Examples",
    "Keyword Args",
    "Keyword Arguments",
    "Note",
    "Notes",
    "Other Parameters",
    "Parameters",
    "Raises",
    "References",
    "Returns",
    "See Also",
    "Todo",
    "Warning",
    "Warnings",
    "Yields",
})

# Pattern to match section headers
SECTION_HEADER_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(s) for s in GOOGLE_STYLE_SECTIONS) + r"):\s*$",
    re.MULTILINE,
)


def _parse_google_style_sections(docstring: str) -> dict[str, str]:
    """Parse Google-style docstring sections.

    Args:
        docstring: The docstring text to parse.

    Returns:
        Dictionary mapping section names to their content.
    """
    if not docstring:
        return {}

    sections: dict[str, str] = {}
    lines = docstring.split("\n")
    current_section: str | None = None
    current_content: list[str] = []

    for line in lines:
        # Check if this line is a section header
        stripped = line.strip()
        header_match = None
        for section_name in GOOGLE_STYLE_SECTIONS:
            if stripped == f"{section_name}:":
                header_match = section_name
                break

        if header_match:
            # Save previous section if exists
            if current_section and current_content:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = header_match
            current_content = []
        elif current_section is not None:
            current_content.append(line)

    # Save last section
    if current_section and current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def _get_function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Extract function signature from AST node.

    Args:
        node: AST function definition node.

    Returns:
        String representation of the function signature.
    """
    args: list[str] = []

    # Handle positional-only args (Python 3.8+)
    for arg in node.args.posonlyargs:
        args.append(arg.arg)

    # Handle regular args
    num_defaults = len(node.args.defaults)
    num_args = len(node.args.args)
    for i, arg in enumerate(node.args.args):
        arg_str = arg.arg
        # Check if this arg has a default
        default_idx = i - (num_args - num_defaults)
        if default_idx >= 0:
            arg_str += "=..."
        args.append(arg_str)

    # Handle *args
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")

    # Handle keyword-only args
    for i, arg in enumerate(node.args.kwonlyargs):
        arg_str = arg.arg
        if node.args.kw_defaults[i] is not None:
            arg_str += "=..."
        args.append(arg_str)

    # Handle **kwargs
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")

    return f"({', '.join(args)})"


def _get_base_names(node: ast.ClassDef) -> list[str]:
    """Extract base class names from class definition.

    Args:
        node: AST class definition node.

    Returns:
        List of base class names.
    """
    bases: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            # Handle module.ClassName
            parts: list[str] = []
            current: Any = base
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            bases.append(".".join(reversed(parts)))
        elif isinstance(base, ast.Subscript):
            # Handle Generic[T] style
            if isinstance(base.value, ast.Name):
                bases.append(base.value.id)
    return bases


def _get_method_names(node: ast.ClassDef) -> list[str]:
    """Extract method names from class definition.

    Args:
        node: AST class definition node.

    Returns:
        List of method names.
    """
    methods: list[str] = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(item.name)
    return methods


def extract_docstrings(path: Path) -> list[DocstringEntry]:
    """Extract docstrings from a Python file.

    Parses the file using AST and extracts docstrings from:
    - Module level
    - Class definitions (with base classes and method names)
    - Function definitions (with signatures)
    - Method definitions (with signatures)

    Google-style docstring sections (Args, Returns, Raises, Examples) are parsed
    and made available in the `sections` field.

    Args:
        path: Path to the Python file.

    Returns:
        List of DocstringEntry objects.

    Raises:
        FileNotFoundError: If the file does not exist.

    Examples:
        >>> entries = extract_docstrings(Path("module.py"))
        >>> for e in entries:
        ...     print(f"{e.entry_type}: {e.name} (line {e.line_number})")
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    content = path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Return empty list for files with syntax errors
        return []

    entries: list[DocstringEntry] = []

    # Extract module docstring
    module_docstring = ast.get_docstring(tree)
    if module_docstring:
        entries.append(
            DocstringEntry(
                name=path.stem,
                entry_type="module",
                docstring=module_docstring,
                source_path=path,
                line_number=1,
                sections=_parse_google_style_sections(module_docstring),
            )
        )

    # Walk the AST
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            docstring = ast.get_docstring(node)
            if docstring:
                entries.append(
                    DocstringEntry(
                        name=node.name,
                        entry_type="class",
                        docstring=docstring,
                        source_path=path,
                        line_number=node.lineno,
                        bases=_get_base_names(node),
                        methods=_get_method_names(node),
                        sections=_parse_google_style_sections(docstring),
                    )
                )

            # Extract method docstrings
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_docstring = ast.get_docstring(item)
                    if method_docstring:
                        entries.append(
                            DocstringEntry(
                                name=item.name,
                                entry_type="method",
                                docstring=method_docstring,
                                source_path=path,
                                line_number=item.lineno,
                                signature=_get_function_signature(item),
                                sections=_parse_google_style_sections(method_docstring),
                            )
                        )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check if this is a top-level function (not a method)
            # We already handle methods inside class bodies above
            # ast.walk visits all nodes, so we need to check parent
            # Since ast.walk doesn't provide parent info, we check if we've
            # already added this function as a method by checking all class bodies
            is_method = False
            for other_node in ast.walk(tree):
                if isinstance(other_node, ast.ClassDef):
                    for item in other_node.body:
                        if item is node:
                            is_method = True
                            break
                if is_method:
                    break

            if not is_method:
                docstring = ast.get_docstring(node)
                if docstring:
                    entries.append(
                        DocstringEntry(
                            name=node.name,
                            entry_type="function",
                            docstring=docstring,
                            source_path=path,
                            line_number=node.lineno,
                            signature=_get_function_signature(node),
                            sections=_parse_google_style_sections(docstring),
                        )
                    )

    return entries
