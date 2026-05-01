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

REQUIRED_PAGES = {
    "docs/index.md",
    "docs/start-here/index.md",
    "docs/get-started/index.md",
    "docs/get-started/first-platform.md",
    "docs/get-started/first-data-product.md",
    "docs/platform-engineers/index.md",
    "docs/platform-engineers/first-platform.md",
    "docs/platform-engineers/validate-platform.md",
    "docs/data-engineers/index.md",
    "docs/data-engineers/first-data-product.md",
    "docs/data-engineers/validate-data-product.md",
    "docs/demo/index.md",
    "docs/demo/customer-360.md",
    "docs/demo/customer-360-validation.md",
    "docs/architecture/capability-status.md",
    "docs/reference/index.md",
    "docs/contributing/index.md",
    "docs/contributing/devpod-hetzner.md",
    "docs/contributing/testing.md",
    "docs/contributing/troubleshooting.md",
    "docs/contributing/documentation-standards.md",
    "docs/releases/v0.1.0-alpha.1-checklist.md",
}

REQUIRED_MANIFEST_SOURCES = {
    "docs/index.md",
    "docs/start-here/index.md",
    "docs/platform-engineers/index.md",
    "docs/platform-engineers/first-platform.md",
    "docs/platform-engineers/validate-platform.md",
    "docs/data-engineers/index.md",
    "docs/data-engineers/first-data-product.md",
    "docs/data-engineers/validate-data-product.md",
    "docs/demo/customer-360.md",
    "docs/architecture/capability-status.md",
    "docs/reference/index.md",
    "docs/contributing/index.md",
    "docs/contributing/devpod-hetzner.md",
    "docs/contributing/testing.md",
    "docs/contributing/troubleshooting.md",
    "docs/contributing/documentation-standards.md",
    "docs/releases/v0.1.0-alpha.1-checklist.md",
}

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
RAW_HTML_HREF_RE = re.compile(r"<a\s+[^>]*\bhref\s*=\s*(['\"])(.*?)\1", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

REQUIRED_TUTORIAL_HEADINGS = {
    "docs/platform-engineers/first-platform.md": (
        "Prerequisites",
        "1. Choose Your Environment",
        "2. Render The Platform",
        "3. Install The Platform",
        "4. Wait For Services",
        "5. Draft The Environment Contract",
        "6. Validate The Platform",
        "7. Prove The Full Demo",
    ),
    "docs/platform-engineers/validate-platform.md": (
        "Platform Health",
        "Service Access",
        "Platform Evidence",
        "Customer 360 Platform Evidence",
        "Publish The Contract, Not A Chat Message",
    ),
    "docs/data-engineers/first-data-product.md": (
        "Prerequisites",
        "1. Inspect The Environment Contract",
        "2. Inspect The Data Product",
        "3. Review The dbt Models",
        "4. Compile The Product For The Alpha Runtime Contract",
        "5. Package A Runtime Artifact",
        "6. Deploy Through Your Organization's Approved Path",
        "7. Validate The Product",
        "8. Then Run Customer 360",
    ),
    "docs/data-engineers/validate-data-product.md": (
        "Business Output Evidence",
        "Runtime Evidence",
        "Lineage And Telemetry Evidence",
        "Escalation Boundary",
    ),
    "docs/contributing/devpod-hetzner.md": (
        "Prerequisites",
        "What This Does",
        "Steps",
        "Expected Output",
        "Port-Forward Ownership",
        "Troubleshooting",
        "Cleanup",
    ),
    "docs/contributing/troubleshooting.md": (
        "Prerequisites",
        "What This Does",
        "Steps",
        "Expected Output",
        "Troubleshooting",
        "Evidence To Capture",
    ),
}


def _manifest_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for section in manifest.get("sections", []):
        if not isinstance(section, dict):
            continue
        for item in section.get("items", []):
            if isinstance(item, dict):
                items.append(item)
    return items


def _manifest_string_list(manifest: dict[str, Any], key: str) -> tuple[str, ...]:
    values = manifest.get(key, [])
    if not isinstance(values, list):
        return ()
    return tuple(value for value in values if isinstance(value, str))


def _is_included_by_prefix(source: str, prefixes: tuple[str, ...]) -> bool:
    return any(source == prefix or source.startswith(prefix) for prefix in prefixes)


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
        if source in sources:
            errors.append(f"Duplicate docs manifest source: {source}")
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


def _without_fenced_code_blocks(markdown: str) -> str:
    """Return Markdown content with fenced code blocks removed."""
    lines: list[str] = []
    in_fenced_code_block = False
    fence_marker = ""

    for line in markdown.splitlines(keepends=True):
        stripped = line.lstrip()
        current_marker = stripped[:3]
        if current_marker in {"```", "~~~"}:
            if not in_fenced_code_block:
                in_fenced_code_block = True
                fence_marker = current_marker
            elif current_marker == fence_marker:
                in_fenced_code_block = False
                fence_marker = ""
            continue

        if not in_fenced_code_block:
            lines.append(line)

    return "".join(lines)


def _validate_doc_links(
    root: Path,
    doc_path: str,
    exclude_prefixes: tuple[str, ...] = (),
) -> list[str]:
    source = root / doc_path
    if not source.exists():
        return []

    source_parent = posixpath.dirname(doc_path)
    errors: list[str] = []
    markdown = source.read_text()
    for match in MARKDOWN_LINK_RE.finditer(markdown):
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
        elif _is_included_by_prefix(resolved, exclude_prefixes):
            errors.append(
                f"Published docs link to excluded docs in {doc_path}: {link_target} -> {resolved}",
            )

    for match in RAW_HTML_HREF_RE.finditer(_without_fenced_code_blocks(markdown)):
        raw_target = match.group(2).strip()
        if not raw_target or raw_target.startswith("#"):
            continue

        parsed = urlparse(raw_target)
        if parsed.scheme or parsed.netloc:
            continue

        errors.append(
            f"Raw HTML local href in {doc_path}: {raw_target}; "
            "use Markdown links for internal docs",
        )

    return errors


def _validate_required_headings(root: Path, doc_path: str) -> list[str]:
    required_headings = REQUIRED_TUTORIAL_HEADINGS.get(doc_path)
    if required_headings is None:
        return []

    source = root / doc_path
    if not source.exists():
        return []

    headings = {title for level, title in HEADING_RE.findall(source.read_text()) if level == "##"}
    return [
        f"Missing required heading in {doc_path}: ## {heading}"
        for heading in required_headings
        if heading not in headings
    ]


def _docs_to_validate(root: Path, manifest_sources: set[str]) -> list[str]:
    docs_root = root / "docs"
    docs: set[str] = set(manifest_sources)
    manifest_path = root / "docs-site/docs-manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    include_prefixes = _manifest_string_list(manifest, "includePrefixes")
    exclude_prefixes = _manifest_string_list(manifest, "excludePrefixes")

    if docs_root.exists():
        for doc_path in sorted(docs_root.rglob("*.md")):
            relative = doc_path.relative_to(root).as_posix()
            if _is_included_by_prefix(
                relative,
                include_prefixes,
            ) and not _is_included_by_prefix(relative, exclude_prefixes):
                docs.add(relative)

    return sorted(docs)


def validate_docs_navigation(root: Path) -> list[str]:
    """Return validation errors for alpha-critical docs navigation."""
    manifest_sources, errors = _validate_manifest(root)
    manifest_path = root / "docs-site/docs-manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    exclude_prefixes = _manifest_string_list(manifest, "excludePrefixes")

    for required in sorted(REQUIRED_PAGES):
        if not (root / required).exists():
            errors.append(f"Missing docs page: {required}")

    for required in sorted(REQUIRED_MANIFEST_SOURCES):
        if required not in manifest_sources:
            errors.append(f"Missing docs manifest entry: {required}")

    for doc_path in _docs_to_validate(root, manifest_sources):
        errors.extend(_validate_doc_links(root, doc_path, exclude_prefixes))
        errors.extend(_validate_required_headings(root, doc_path))

    return errors


def main() -> int:
    errors = validate_docs_navigation(Path.cwd())
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
