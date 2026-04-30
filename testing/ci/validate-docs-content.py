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
UNCAVEATED_ALPHA_CLAIMS = (
    (
        re.compile(r"without rewrites", re.IGNORECASE),
        "uncaveated Data Mesh migration language 'without rewrites'",
    ),
    (
        re.compile(r"Data Mesh seamlessly", re.IGNORECASE),
        "uncaveated Data Mesh migration language 'Data Mesh seamlessly'",
    ),
)
DOCKER_COMPOSE_PRODUCT_PATHS = (
    (
        re.compile(r"Docker Compose setup", re.IGNORECASE),
        "Docker Compose setup presented as a product path",
    ),
    (
        re.compile(r"\bdocker\s+compose\s+up\b", re.IGNORECASE),
        "'docker compose up' presented as a product path",
    ),
    (
        re.compile(r"\bDocker Compose\b.*\b(development|evaluation)\b", re.IGNORECASE),
        "Docker Compose presented as a development or evaluation product path",
    ),
    (
        re.compile(r"\b(development|evaluation)\b.*\bDocker Compose\b", re.IGNORECASE),
        "Docker Compose presented as a development or evaluation product path",
    ),
)
FLOE_DEV_PRODUCT_PATH = (
    re.compile(r"\bfloe\s+dev\b", re.IGNORECASE),
    "unsupported CLI command 'floe dev' presented as a product path",
)
UNSUPPORTED_ALPHA_LIFECYCLE_COMMAND_RE = re.compile(
    r"(?:^|[\s`$])(?P<command>"
    r"floe\s+init\b|"
    r"floe\s+compile\b|"
    r"floe\s+run\b|"
    r"floe\s+test\b|"
    r"floe\s+platform\s+test\b"
    r")",
    re.IGNORECASE,
)
UNSUPPORTED_ALPHA_LIFECYCLE_ALLOWED_CONTEXT_RE = re.compile(
    r"\b("
    r"planned|stub|target|target-state|historical|not implemented|not current|"
    r"not the current|not yet implemented|not alpha-supported|non-current"
    r")\b",
    re.IGNORECASE,
)
UNSUPPORTED_ALPHA_LIFECYCLE_GUARD_PATH_PREFIXES = (
    "README.md",
    "docs/index.md",
    "docs/start-here/",
    "docs/platform-engineers/",
    "docs/data-engineers/",
    "docs/get-started/",
    "docs/demo/",
    "docs/contracts/",
    "docs/architecture/",
    "docs/guides/",
    "docs/reference/",
    "docs/guides/deployment/",
)
PLUGIN_COUNT_RE = re.compile(
    r"\b(?P<count>\d+)\s+plugin\s+(?P<noun>types?|categor(?:y|ies))\b",
    re.IGNORECASE,
)
NEGATIVE_OR_PLANNED_CONTEXT_RE = re.compile(
    r"\b("
    r"not supported|unsupported|not alpha-supported|not implemented|planned|historical|"
    r"deprecated|rejected|was rejected|alternative|not a current|do not run|"
    r"no Docker Compose|creates testing parity issues|parity issues|failure mode"
    r")\b",
    re.IGNORECASE,
)
CHART_METADATA_RULES = (
    (
        re.compile(r"Production-ready", re.IGNORECASE),
        "chart metadata must not claim production-ready status",
    ),
    (
        re.compile(r"floe-runtime"),
        "chart metadata must point to Obsidian-Owl/floe, not floe-runtime",
    ),
    (
        re.compile(r'appVersion:\s*["\']?1\.0\.0["\']?'),
        "chart metadata must not use stale appVersion 1.0.0",
    ),
)
EXPECTED_FLOE_PLATFORM_APP_VERSION = "0.1.0-alpha.1"


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


def _guards_unsupported_alpha_lifecycle_commands(rel_path: str) -> bool:
    """Return whether unsupported lifecycle commands are user-facing in this path."""
    if rel_path.startswith("docs/architecture/adr/"):
        return False
    return any(
        rel_path == prefix or rel_path.startswith(prefix)
        for prefix in UNSUPPORTED_ALPHA_LIFECYCLE_GUARD_PATH_PREFIXES
    )


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
        rel_path_str = rel_path.as_posix()

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

            for pattern, message in UNCAVEATED_ALPHA_CLAIMS:
                if pattern.search(line):
                    errors.append(f"{rel_path}:{line_number}: {message}")

            has_negative_or_planned_context = bool(NEGATIVE_OR_PLANNED_CONTEXT_RE.search(line))
            for pattern, message in DOCKER_COMPOSE_PRODUCT_PATHS:
                if pattern.search(line) and not has_negative_or_planned_context:
                    errors.append(f"{rel_path}:{line_number}: {message}")

            floe_dev_pattern, floe_dev_message = FLOE_DEV_PRODUCT_PATH
            if floe_dev_pattern.search(line) and not has_negative_or_planned_context:
                errors.append(f"{rel_path}:{line_number}: {floe_dev_message}")

            if _guards_unsupported_alpha_lifecycle_commands(rel_path_str):
                for match in UNSUPPORTED_ALPHA_LIFECYCLE_COMMAND_RE.finditer(line):
                    if UNSUPPORTED_ALPHA_LIFECYCLE_ALLOWED_CONTEXT_RE.search(line):
                        continue
                    command = " ".join(match.group("command").split())
                    errors.append(
                        f"{rel_path}:{line_number}: {command!r} is not a supported current "
                        "alpha workflow; use 'floe platform compile', 'make compile-demo', "
                        "or mark it planned/stub/target-state"
                    )

            if _is_historical_adr_line(path, active_heading):
                continue

            for match in PLUGIN_COUNT_RE.finditer(line):
                actual_count = int(match.group("count"))
                if actual_count != expected_count:
                    errors.append(
                        f"{rel_path}:{line_number}: plugin count {actual_count} does not "
                        f"match implementation truth; expected {expected_count} plugin categories"
                    )

    errors.extend(_validate_chart_metadata(root))

    return sorted(errors)


def _validate_chart_metadata(root: Path) -> list[str]:
    """Validate chart metadata that is surfaced in chart docs and Helm NOTES."""
    chart_path = root / "charts" / "floe-platform" / "Chart.yaml"
    if not chart_path.exists():
        return []

    errors: list[str] = []
    rel_path = chart_path.relative_to(root)
    lines = chart_path.read_text().splitlines()
    app_version_seen = False

    for line_number, line in enumerate(lines, start=1):
        for pattern, message in CHART_METADATA_RULES:
            if pattern.search(line):
                errors.append(f"{rel_path}:{line_number}: {message}")

        match = re.match(r"\s*appVersion:\s*[\"']?([^\"'\s]+)[\"']?\s*$", line)
        if match:
            app_version_seen = True
            app_version = match.group(1)
            if app_version != EXPECTED_FLOE_PLATFORM_APP_VERSION:
                errors.append(
                    f"{rel_path}:{line_number}: chart appVersion {app_version!r} must match "
                    f"alpha release {EXPECTED_FLOE_PLATFORM_APP_VERSION!r}"
                )

    if not app_version_seen:
        errors.append(f"{rel_path}: missing appVersion")

    return errors


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
