#!/usr/bin/env python3
"""Validate alpha-critical documentation pages are present and navigable."""

from __future__ import annotations

import posixpath
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

REQUIRED_DOCS = {
    "docs/index.md",
    "docs/start-here/index.md",
    "docs/get-started/index.md",
    "docs/get-started/first-platform.md",
    "docs/get-started/first-data-product.md",
    "docs/demo/index.md",
    "docs/demo/customer-360.md",
    "docs/demo/customer-360-validation.md",
    "docs/operations/devpod-hetzner.md",
    "docs/operations/troubleshooting.md",
    "docs/reference/index.md",
    "docs/contributing/index.md",
    "docs/contributing/documentation-standards.md",
    "docs/releases/v0.1.0-alpha.1-checklist.md",
}

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _walk_nav_items(items: list[Any]) -> set[str]:
    paths: set[str] = set()
    for item in items:
        if isinstance(item, str):
            paths.add(item)
        elif isinstance(item, dict):
            for value in item.values():
                if isinstance(value, str):
                    paths.add(value)
                elif isinstance(value, list):
                    paths.update(_walk_nav_items(value))
    return paths


def _link_target(raw_target: str) -> str | None:
    target_parts = raw_target.strip().split()
    if not target_parts:
        return None

    target = target_parts[0]
    if not target or target.startswith("#") or target.startswith("/"):
        return None

    parsed = urlparse(target)
    if parsed.scheme:
        return None

    target_path = target.split("#", 1)[0].split("?", 1)[0]
    if not target_path or Path(target_path).suffix != ".md":
        return None

    return target_path


def _validate_required_doc_links(root: Path, required: str) -> list[str]:
    source = root / required
    if not source.exists():
        return []

    source_parent = posixpath.dirname(required)
    errors: list[str] = []
    for match in MARKDOWN_LINK_RE.finditer(source.read_text()):
        link_target = _link_target(match.group(1))
        if link_target is None:
            continue

        resolved = posixpath.normpath(posixpath.join(source_parent, link_target))
        if not (root / resolved).exists():
            errors.append(
                f"Broken docs link in {required}: {link_target} -> {resolved}",
            )

    return errors


def validate_docs_navigation(root: Path) -> list[str]:
    """Return validation errors for alpha-critical docs navigation."""
    mkdocs_path = root / "mkdocs.yml"
    if not mkdocs_path.exists():
        return ["Missing mkdocs.yml"]

    config = yaml.safe_load(mkdocs_path.read_text()) or {}
    nav_paths = {f"docs/{path}" for path in _walk_nav_items(config.get("nav", []))}
    errors: list[str] = []

    for required in sorted(REQUIRED_DOCS):
        if not (root / required).exists():
            errors.append(f"Missing docs page: {required}")
        if required not in nav_paths:
            errors.append(f"Missing docs nav entry: {required}")
        errors.extend(_validate_required_doc_links(root, required))

    return errors


def main() -> int:
    errors = validate_docs_navigation(Path.cwd())
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
