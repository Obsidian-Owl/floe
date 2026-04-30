from __future__ import annotations

import json
from pathlib import Path

import pytest

from testing.ci.validate_docs_navigation import validate_docs_navigation

REQUIRED_PAGES = [
    "index.md",
    "start-here/index.md",
    "get-started/index.md",
    "get-started/first-platform.md",
    "get-started/first-data-product.md",
    "platform-engineers/index.md",
    "platform-engineers/first-platform.md",
    "platform-engineers/validate-platform.md",
    "data-engineers/index.md",
    "data-engineers/first-data-product.md",
    "data-engineers/validate-data-product.md",
    "demo/index.md",
    "demo/customer-360.md",
    "demo/customer-360-validation.md",
    "architecture/capability-status.md",
    "reference/index.md",
    "contributing/index.md",
    "contributing/devpod-hetzner.md",
    "contributing/testing.md",
    "contributing/troubleshooting.md",
    "contributing/documentation-standards.md",
    "releases/v0.1.0-alpha.1-checklist.md",
]

REQUIRED_MANIFEST_SOURCES = [
    "index.md",
    "start-here/index.md",
    "platform-engineers/index.md",
    "platform-engineers/first-platform.md",
    "platform-engineers/validate-platform.md",
    "data-engineers/index.md",
    "data-engineers/first-data-product.md",
    "data-engineers/validate-data-product.md",
    "demo/customer-360.md",
    "architecture/capability-status.md",
    "reference/index.md",
    "contributing/index.md",
    "contributing/devpod-hetzner.md",
    "contributing/testing.md",
    "contributing/troubleshooting.md",
    "contributing/documentation-standards.md",
    "releases/v0.1.0-alpha.1-checklist.md",
]

PLATFORM_FIRST_DOC = """# Deploy Your First Platform

## Prerequisites

## 1. Confirm Your Cluster Context

## 2. Choose The Deployment Mode

## 3. Prepare Platform Configuration

## 4. Install Floe

## 5. Wait For Platform Services

## 6. Validate The Platform

## Cloud Provider Examples
"""

PLATFORM_VALIDATE_DOC = """# Validate Your Platform

## Platform Health

## Service Access

## Customer 360 Platform Evidence

## What To Hand To Data Engineers
"""

DATA_FIRST_DOC = """# Build Your First Data Product

## Prerequisites

## 1. Inspect The Product Configuration

## 2. Validate The Product

## 3. Compile The Product

## 4. Run The Product

## 5. Validate The Product Outputs
"""

DATA_VALIDATE_DOC = """# Validate Your Data Product

## Validate Business Outputs

## Inspect Orchestration

## Inspect Storage

## Inspect Lineage And Traces

## Troubleshooting
"""

CONTRIBUTOR_TUTORIAL_DOC = """# {title}

## Prerequisites

## What This Does

## Steps

## Expected Output

## Port-Forward Ownership

## Troubleshooting

## Cleanup
"""

TROUBLESHOOTING_DOC = """# Troubleshooting

## Prerequisites

## What This Does

## Steps

## Expected Output

## Troubleshooting

## Evidence To Capture
"""

TUTORIAL_DOCS = {
    "platform-engineers/first-platform.md": PLATFORM_FIRST_DOC,
    "platform-engineers/validate-platform.md": PLATFORM_VALIDATE_DOC,
    "data-engineers/first-data-product.md": DATA_FIRST_DOC,
    "data-engineers/validate-data-product.md": DATA_VALIDATE_DOC,
    "contributing/devpod-hetzner.md": CONTRIBUTOR_TUTORIAL_DOC,
    "contributing/troubleshooting.md": TROUBLESHOOTING_DOC,
}


def _write_required_docs(root: Path) -> None:
    docs = root / "docs"
    for relative in REQUIRED_PAGES:
        path = docs / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        template = TUTORIAL_DOCS.get(relative, "# {title}\n")
        path.write_text(template.format(title=path.stem))


def _write_manifest(root: Path, docs: list[str] | None = None) -> None:
    manifest_docs = docs if docs is not None else REQUIRED_MANIFEST_SOURCES
    manifest = {
        "includePrefixes": [
            "docs/architecture/",
            "docs/contributing/",
            "docs/data-engineers/",
            "docs/demo/",
            "docs/get-started/",
            "docs/platform-engineers/",
            "docs/reference/",
            "docs/releases/",
            "docs/start-here/",
        ],
        "sections": [
            {
                "label": "Persona docs",
                "items": [
                    {
                        "title": relative.removesuffix(".md"),
                        "source": f"docs/{relative}",
                        "slug": relative.removesuffix("/index.md").removesuffix(".md"),
                    }
                    for relative in manifest_docs
                ],
            },
        ],
    }
    manifest_path = root / "docs-site/docs-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest))


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_missing_required_page(tmp_path: Path) -> None:
    """Navigation validation reports alpha-critical pages missing from docs."""
    _write_manifest(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n")

    errors = validate_docs_navigation(tmp_path)

    assert "Missing docs page: docs/start-here/index.md" in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_missing_required_manifest_entry(
    tmp_path: Path,
) -> None:
    """Navigation validation reports required pages omitted from the docs manifest."""
    _write_required_docs(tmp_path)
    _write_manifest(
        tmp_path,
        docs=[doc for doc in REQUIRED_MANIFEST_SOURCES if doc != "reference/index.md"],
    )

    errors = validate_docs_navigation(tmp_path)

    assert "Missing docs manifest entry: docs/reference/index.md" in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_rejects_first_platform_without_install_step(
    tmp_path: Path,
) -> None:
    """Navigation validation rejects alpha tutorials missing required headings."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    (tmp_path / "docs/platform-engineers/first-platform.md").write_text(
        "# Deploy Your First Platform\n\n"
        "## Prerequisites\n\n"
        "## 1. Confirm Your Cluster Context\n\n"
        "## 2. Choose The Deployment Mode\n\n"
        "## 3. Prepare Platform Configuration\n\n"
        "## 5. Wait For Platform Services\n\n"
        "## 6. Validate The Platform\n\n"
        "## Cloud Provider Examples\n",
    )

    errors = validate_docs_navigation(tmp_path)

    assert (
        "Missing required heading in docs/platform-engineers/first-platform.md: ## 4. Install Floe"
    ) in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_missing_manifest_source(
    tmp_path: Path,
) -> None:
    """Navigation validation reports manifest entries pointing at missing sources."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path, docs=[*REQUIRED_MANIFEST_SOURCES, "missing.md"])

    errors = validate_docs_navigation(tmp_path)

    assert "Missing docs manifest source: docs/missing.md" in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_rejects_non_markdown_manifest_source(
    tmp_path: Path,
) -> None:
    """Navigation validation rejects manifest sources Starlight cannot serve."""
    _write_required_docs(tmp_path)
    non_markdown_source = tmp_path / "docs/downloads/readme.txt"
    non_markdown_source.parent.mkdir(parents=True)
    non_markdown_source.write_text("Not a docs page.\n")
    _write_manifest(tmp_path, docs=[*REQUIRED_MANIFEST_SOURCES, "downloads/readme.txt"])

    errors = validate_docs_navigation(tmp_path)

    assert ("Invalid docs manifest source extension: docs/downloads/readme.txt") in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_duplicate_manifest_slug(
    tmp_path: Path,
) -> None:
    """Navigation validation reports duplicate generated slugs."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    manifest_path = tmp_path / "docs-site/docs-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sections"][0]["items"][1]["slug"] = "index"
    manifest_path.write_text(json.dumps(manifest))

    errors = validate_docs_navigation(tmp_path)

    assert "Duplicate docs manifest slug: index" in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_duplicate_manifest_source(
    tmp_path: Path,
) -> None:
    """Navigation validation reports manifest source reuse across routes."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    manifest_path = tmp_path / "docs-site/docs-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sections"][0]["items"][1]["source"] = "docs/index.md"
    manifest["sections"][0]["items"][1]["slug"] = "start-here"
    manifest_path.write_text(json.dumps(manifest))

    errors = validate_docs_navigation(tmp_path)

    assert "Duplicate docs manifest source: docs/index.md" in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_accepts_required_alpha_pages(tmp_path: Path) -> None:
    """Navigation validation passes when alpha-critical pages exist in the manifest."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)

    assert validate_docs_navigation(tmp_path) == []


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_allows_bridge_pages_outside_primary_manifest(
    tmp_path: Path,
) -> None:
    """Bridge pages must exist and link-check without being primary nav entries."""
    _write_required_docs(tmp_path)
    _write_manifest(
        tmp_path,
        docs=[doc for doc in REQUIRED_MANIFEST_SOURCES if not doc.startswith("get-started/")],
    )

    assert validate_docs_navigation(tmp_path) == []


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_broken_required_doc_link(
    tmp_path: Path,
) -> None:
    """Navigation validation reports broken relative Markdown links."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    (tmp_path / "docs/start-here/index.md").write_text(
        "# Start Here\n\nSee [missing](../missing.md).\n",
    )

    errors = validate_docs_navigation(tmp_path)

    assert (
        "Broken docs link in docs/start-here/index.md: ../missing.md -> docs/missing.md"
    ) in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_site_root_markdown_link(
    tmp_path: Path,
) -> None:
    """Navigation validation rejects site-root Markdown links."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    (tmp_path / "docs/start-here/index.md").write_text(
        "# Start Here\n\nSee [testing](/TESTING.md).\n",
    )

    errors = validate_docs_navigation(tmp_path)

    assert ("Site-root Markdown link in docs/start-here/index.md: /TESTING.md") in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_rejects_raw_html_local_href(
    tmp_path: Path,
) -> None:
    """Navigation validation rejects local raw HTML hrefs that bypass link rewriting."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    (tmp_path / "docs/demo/customer-360-validation.md").write_text(
        '# Validation\n\n<a href="../contributing/devpod-hetzner.md">DevPod</a>\n',
    )

    errors = validate_docs_navigation(tmp_path)

    assert (
        "Raw HTML local href in docs/demo/customer-360-validation.md: "
        "../contributing/devpod-hetzner.md; use Markdown links for internal docs"
    ) in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_allows_raw_html_external_href(
    tmp_path: Path,
) -> None:
    """Navigation validation allows raw HTML hrefs for external badge-style links."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    (tmp_path / "docs/demo/customer-360-validation.md").write_text(
        '# Validation\n\n<a href="https://example.com">External</a>\n',
    )

    assert validate_docs_navigation(tmp_path) == []


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_checks_non_required_docs(
    tmp_path: Path,
) -> None:
    """Navigation validation checks active guide docs beyond required release pages."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    manifest_path = tmp_path / "docs-site/docs-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["includePrefixes"] = ["docs/guides/"]
    manifest_path.write_text(json.dumps(manifest))
    extra_doc = tmp_path / "docs/guides/testing/index.md"
    extra_doc.parent.mkdir(parents=True)
    extra_doc.write_text("# Testing\n\nSee [missing](../missing.md).\n")

    errors = validate_docs_navigation(tmp_path)

    assert (
        "Broken docs link in docs/guides/testing/index.md: ../missing.md -> docs/guides/missing.md"
    ) in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_checks_all_published_docs(
    tmp_path: Path,
) -> None:
    """Navigation validation checks docs published via manifest include prefixes."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    manifest_path = tmp_path / "docs-site/docs-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["includePrefixes"] = ["docs/architecture/"]
    manifest_path.write_text(json.dumps(manifest))
    published_doc = tmp_path / "docs/architecture/published.md"
    published_doc.parent.mkdir(parents=True, exist_ok=True)
    published_doc.write_text("# Published\n\nSee [missing](missing.md).\n")

    errors = validate_docs_navigation(tmp_path)

    assert (
        "Broken docs link in docs/architecture/published.md: missing.md -> "
        "docs/architecture/missing.md"
    ) in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_accepts_valid_required_doc_link(
    tmp_path: Path,
) -> None:
    """Navigation validation accepts existing relative Markdown links."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    (tmp_path / "docs/start-here/index.md").write_text(
        "# Start Here\n\nSee [home](../index.md).\n",
    )

    assert validate_docs_navigation(tmp_path) == []


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_ignores_whitespace_only_doc_link(
    tmp_path: Path,
) -> None:
    """Navigation validation ignores placeholder Markdown links."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    (tmp_path / "docs/start-here/index.md").write_text(
        "# Start Here\n\nSee [placeholder]( ).\n",
    )

    assert validate_docs_navigation(tmp_path) == []
