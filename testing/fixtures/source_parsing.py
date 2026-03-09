"""Shared helpers for structural/source-parsing tests.

These utilities extract function source code via AST and strip comments
for structural validation of E2E test patterns.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


def get_function_source(file_path: Path, func_name: str) -> str:
    """Extract the source text of a specific method from a Python file.

    Parses the file's AST, locates the function/method by name, and returns
    its raw source lines. Works for methods nested inside classes.

    Args:
        file_path: Path to the Python source file.
        func_name: Name of the function or method to extract.

    Returns:
        The raw source text of the function body.

    Raises:
        ValueError: If the function is not found in the file.
    """
    source = file_path.read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                lines = source.splitlines()
                # node.lineno is 1-based, node.end_lineno is inclusive
                start = node.lineno - 1
                end = node.end_lineno if node.end_lineno else start + 1
                return "\n".join(lines[start:end])

    msg = f"Function {func_name!r} not found in {file_path}"
    raise ValueError(msg)


def strip_comments_and_docstrings(source: str) -> str:
    """Remove comments and docstrings from Python source, leaving executable code.

    This prevents passing structural tests by adding keywords in a comment
    (e.g., ``# TODO: check manifest.yaml``) without writing actual code.

    Limitations:
        The inline comment regex ``#[^"']*$`` is a heuristic. It correctly
        handles most cases but may mis-strip lines where ``#`` appears after
        a closing quote on the same line. This is acceptable because the
        patterns being validated are straightforward assignments and function
        calls, not complex string literals with inline comments.

    Args:
        source: Raw Python source text.

    Returns:
        Source with comments and docstrings removed.
    """
    # Remove single-line comments (# ...)
    code_lines: list[str] = []
    for line in source.splitlines():
        stripped = re.sub(r'#[^"\']*$', "", line)
        code_lines.append(stripped)
    code = "\n".join(code_lines)

    # Remove triple-quoted strings (docstrings)
    code = re.sub(r'"""[\s\S]*?"""', '""""""', code)
    code = re.sub(r"'''[\s\S]*?'''", "''''''", code)

    return code
