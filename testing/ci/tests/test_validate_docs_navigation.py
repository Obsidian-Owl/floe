from __future__ import annotations

import json
from pathlib import Path

import pytest

from testing.ci.validate_docs_navigation import validate_docs_navigation

REQUIRED_DOCS = [
    "index.md",
    "start-here/index.md",
    "get-started/index.md",
    "get-started/first-platform.md",
    "get-started/first-data-product.md",
    "demo/index.md",
    "demo/customer-360.md",
    "demo/customer-360-validation.md",
    "operations/devpod-hetzner.md",
    "operations/troubleshooting.md",
    "reference/index.md",
    "contributing/index.md",
    "contributing/documentation-standards.md",
    "releases/v0.1.0-alpha.1-checklist.md",
]

BASE_TUTORIAL_DOC = """# {title}

## Prerequisites

## What This Does

## Steps

## Expected Output

## Troubleshooting
"""

INFRA_TUTORIAL_DOC = f"""{BASE_TUTORIAL_DOC}

## Cleanup
"""

TUTORIAL_DOCS = {
    "get-started/first-platform.md": INFRA_TUTORIAL_DOC,
    "get-started/first-data-product.md": BASE_TUTORIAL_DOC,
    "operations/devpod-hetzner.md": INFRA_TUTORIAL_DOC,
    "operations/troubleshooting.md": BASE_TUTORIAL_DOC,
}


def _write_required_docs(root: Path) -> None:
    docs = root / "docs"
    for relative in REQUIRED_DOCS:
        path = docs / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        template = TUTORIAL_DOCS.get(relative, "# {title}\n")
        path.write_text(template.format(title=path.stem))


def _write_manifest(root: Path, docs: list[str] | None = None) -> None:
    manifest_docs = docs if docs is not None else REQUIRED_DOCS
    manifest = {
        "sections": [
            {
                "label": "Alpha",
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
    _write_manifest(tmp_path, docs=[doc for doc in REQUIRED_DOCS if doc != "reference/index.md"])

    errors = validate_docs_navigation(tmp_path)

    assert "Missing docs manifest entry: docs/reference/index.md" in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_rejects_first_platform_without_expected_output(
    tmp_path: Path,
) -> None:
    """Navigation validation rejects alpha tutorials missing required headings."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path)
    (tmp_path / "docs/get-started/first-platform.md").write_text(
        "# Deploy Your First Platform\n\n"
        "## Prerequisites\n\n"
        "## What This Does\n\n"
        "## Steps\n\n"
        "## Troubleshooting\n\n"
        "## Cleanup\n",
    )

    errors = validate_docs_navigation(tmp_path)

    assert (
        "Missing required heading in docs/get-started/first-platform.md: ## Expected Output"
    ) in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_missing_manifest_source(
    tmp_path: Path,
) -> None:
    """Navigation validation reports manifest entries pointing at missing sources."""
    _write_required_docs(tmp_path)
    _write_manifest(tmp_path, docs=[*REQUIRED_DOCS, "missing.md"])

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
    _write_manifest(tmp_path, docs=[*REQUIRED_DOCS, "downloads/readme.txt"])

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
    published_doc.parent.mkdir(parents=True)
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
