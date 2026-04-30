#!/usr/bin/env python3
"""Validate alpha-critical documentation pages are present and navigable."""

from __future__ import annotations

import json
import posixpath
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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

ADDITIONAL_VALIDATED_DOCS = {
    "docs/guides/08-quality.md",
}

VALIDATED_DOC_PREFIXES = ("docs/guides/testing/",)

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _manifest_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for section in manifest.get("sections", []):
        if not isinstance(section, dict):
            continue
        for item in section.get("items", []):
            if isinstance(item, dict):
                items.append(item)
    return items


def _validate_manifest(root: Path) -> tuple[set[str], list[str]]:
    manifest_path = root / "docs-site/docs-manifest.json"
    if not manifest_path.exists():
        return set(), ["Missing docs manifest: docs-site/docs-manifest.json"]

    manifest = json.loads(manifest_path.read_text())
    sources: set[str] = set()
    slugs: set[str] = set()
    errors: list[str] = []

    for item in _manifest_items(manifest):
        source = item.get("source")
        slug = item.get("slug")
        title = item.get("title")

        if not isinstance(source, str) or not source.startswith("docs/"):
            errors.append(f"Invalid docs manifest source: {source!r}")
            continue
        if not source.endswith(".md"):
            errors.append(f"Invalid docs manifest source extension: {source}")
            continue
        if not isinstance(slug, str) or not slug:
            errors.append(f"Invalid docs manifest slug for {source}: {slug!r}")
        elif slug in slugs:
            errors.append(f"Duplicate docs manifest slug: {slug}")
        else:
            slugs.add(slug)
        if not isinstance(title, str) or not title:
            errors.append(f"Invalid docs manifest title for {source}: {title!r}")

        sources.add(source)
        if not (root / source).exists():
            errors.append(f"Missing docs manifest source: {source}")

    return sources, errors


def _raw_link_target(raw_target: str) -> str | None:
    target_parts = raw_target.strip().split()
    if not target_parts:
        return None

    target = target_parts[0]
    if not target or target.startswith("#"):
        return None

    parsed = urlparse(target)
    if parsed.scheme:
        return None

    target_path = target.split("#", 1)[0].split("?", 1)[0]
    if not target_path or Path(target_path).suffix != ".md":
        return None

    return target_path


def _validate_doc_links(root: Path, doc_path: str) -> list[str]:
    source = root / doc_path
    if not source.exists():
        return []

    source_parent = posixpath.dirname(doc_path)
    errors: list[str] = []
    for match in MARKDOWN_LINK_RE.finditer(source.read_text()):
        link_target = _raw_link_target(match.group(1))
        if link_target is None:
            continue

        if link_target.startswith("/"):
            errors.append(f"Site-root Markdown link in {doc_path}: {link_target}")
            continue

        resolved = posixpath.normpath(posixpath.join(source_parent, link_target))
        if not (root / resolved).exists():
            errors.append(
                f"Broken docs link in {doc_path}: {link_target} -> {resolved}",
            )

    return errors


def _docs_to_validate(root: Path, manifest_sources: set[str]) -> list[str]:
    docs_root = root / "docs"
    docs: set[str] = set(manifest_sources)
    docs.update(ADDITIONAL_VALIDATED_DOCS)

    if docs_root.exists():
        for doc_path in sorted(docs_root.rglob("*.md")):
            relative = str(doc_path.relative_to(root))
            if relative.startswith(VALIDATED_DOC_PREFIXES):
                docs.add(relative)

    return sorted(docs)


def validate_docs_navigation(root: Path) -> list[str]:
    """Return validation errors for alpha-critical docs navigation."""
    manifest_sources, errors = _validate_manifest(root)

    for required in sorted(REQUIRED_DOCS):
        if not (root / required).exists():
            errors.append(f"Missing docs page: {required}")
        if required not in manifest_sources:
            errors.append(f"Missing docs manifest entry: {required}")

    for doc_path in _docs_to_validate(root, manifest_sources):
        errors.extend(_validate_doc_links(root, doc_path))

    return errors


def main() -> int:
    errors = validate_docs_navigation(Path.cwd())
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
