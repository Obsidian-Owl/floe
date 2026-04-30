#!/usr/bin/env python3
"""Validate public documentation content for stale or internal-only phrases."""

from __future__ import annotations

import json
import re
from pathlib import Path

from floe_core.plugin_types import PluginType

STALE_RELEASE_PHRASES = (
    "unmerged release-hardening patch",
    "blocked until the release-hardening patch",
    "main@c1f26a1",
)
INTERNAL_AGENT_PHRASES = (
    "ALWAYS USE when",
    "When this skill is invoked",
    "$ARGUMENTS",
    "Context Injection (For Future Claude Instances)",
)
UNSUPPORTED_PUBLIC_CLI_SNIPPETS = (
    (re.compile(r"\bfloe\s+schema\s+export\b"), "unsupported CLI command 'floe schema export'"),
)
PLUGIN_COUNT_RE = re.compile(
    r"\b(?P<count>\d+)\s+plugin\s+(?P<noun>types?|categor(?:y|ies))\b",
    re.IGNORECASE,
)


def _manifest_items(manifest: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    sections = manifest.get("sections", [])
    if not isinstance(sections, list):
        return items

    for section in sections:
        if not isinstance(section, dict):
            continue
        section_items = section.get("items", [])
        if not isinstance(section_items, list):
            continue
        items.extend(item for item in section_items if isinstance(item, dict))

    return items


def _manifest_string_list(manifest: dict[str, object], key: str) -> tuple[str, ...]:
    values = manifest.get(key, [])
    if not isinstance(values, list):
        return ()
    return tuple(value for value in values if isinstance(value, str))


def _is_included_by_prefix(source: str, prefixes: tuple[str, ...]) -> bool:
    return any(source == prefix or source.startswith(prefix) for prefix in prefixes)


def _manifest_public_doc_paths(root: Path) -> list[Path] | None:
    manifest_path = root / "docs-site" / "docs-manifest.json"
    if not manifest_path.exists():
        return None

    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict):
        return []

    include_prefixes = _manifest_string_list(manifest, "includePrefixes")
    exclude_prefixes = _manifest_string_list(manifest, "excludePrefixes")
    public_sources: set[str] = set()

    for item in _manifest_items(manifest):
        source = item.get("source")
        if (
            isinstance(source, str)
            and source.endswith(".md")
            and not _is_included_by_prefix(
                source,
                exclude_prefixes,
            )
        ):
            public_sources.add(source)

    docs_root = root / "docs"
    if docs_root.exists():
        for path in docs_root.rglob("*.md"):
            relative = path.relative_to(root).as_posix()
            if _is_included_by_prefix(
                relative,
                include_prefixes,
            ) and not _is_included_by_prefix(relative, exclude_prefixes):
                public_sources.add(relative)

    return [root / source for source in sorted(public_sources)]


def public_markdown_paths(root: Path) -> list[Path]:
    """Return public Markdown files in deterministic scan order."""
    paths: list[Path] = []
    readme = root / "README.md"
    if readme.exists():
        paths.append(readme)

    manifest_paths = _manifest_public_doc_paths(root)
    if manifest_paths is not None:
        paths.extend(path for path in manifest_paths if path.exists())
        return paths

    docs = root / "docs"
    if docs.exists():
        paths.extend(sorted(docs.rglob("*.md")))

    return paths


def _is_historical_adr_line(path: Path, active_heading: str) -> bool:
    """Allow old plugin counts inside ADR version/history sections."""
    normalized = path.as_posix()
    if "/docs/architecture/adr/" not in normalized:
        return False
    heading = active_heading.casefold()
    return "version" in heading or "history" in heading


def validate_docs_content(
    root: Path,
    *,
    plugin_category_count: int | None = None,
) -> list[str]:
    """Validate public docs and return deterministic file:line errors."""
    expected_count = plugin_category_count
    if expected_count is None:
        expected_count = len(list(PluginType))

    errors: list[str] = []
    root = root.resolve()

    for path in public_markdown_paths(root):
        try:
            rel_path = path.relative_to(root)
        except ValueError:
            rel_path = path

        active_heading = ""
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if line.lstrip().startswith("#"):
                active_heading = line.strip("# \t")

            for phrase in STALE_RELEASE_PHRASES:
                if phrase in line:
                    errors.append(f"{rel_path}:{line_number}: stale release phrase {phrase!r}")

            for phrase in INTERNAL_AGENT_PHRASES:
                if phrase in line:
                    errors.append(
                        f"{rel_path}:{line_number}: internal agent runbook phrase {phrase!r}"
                    )

            for pattern, message in UNSUPPORTED_PUBLIC_CLI_SNIPPETS:
                if pattern.search(line):
                    errors.append(f"{rel_path}:{line_number}: {message}")

            if _is_historical_adr_line(path, active_heading):
                continue

            for match in PLUGIN_COUNT_RE.finditer(line):
                actual_count = int(match.group("count"))
                if actual_count != expected_count:
                    errors.append(
                        f"{rel_path}:{line_number}: plugin count {actual_count} does not "
                        f"match implementation truth; expected {expected_count} plugin categories"
                    )

    return sorted(errors)


def main() -> int:
    """Run validation from the repository root."""
    root = Path(__file__).resolve().parents[2]
    errors = validate_docs_content(root)
    if errors:
        for error in errors:
            print(error)
        return 1

    print("docs content validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
