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

REQUIRED_NAV = (
    "nav:\n"
    "  - Home: index.md\n"
    "  - Start Here:\n"
    "      - start-here/index.md\n"
    "  - Get Started:\n"
    "      - get-started/index.md\n"
    "      - get-started/first-platform.md\n"
    "      - get-started/first-data-product.md\n"
    "  - Demo:\n"
    "      - demo/index.md\n"
    "      - demo/customer-360.md\n"
    "      - demo/customer-360-validation.md\n"
    "  - Operations:\n"
    "      - operations/devpod-hetzner.md\n"
    "      - operations/troubleshooting.md\n"
    "  - Reference:\n"
    "      - reference/index.md\n"
    "  - Contributing:\n"
    "      - contributing/index.md\n"
    "      - contributing/documentation-standards.md\n"
    "  - Releases:\n"
    "      - releases/v0.1.0-alpha.1-checklist.md\n"
)


def _write_required_docs(root: Path) -> None:
    docs = root / "docs"
    for relative in REQUIRED_DOCS:
        path = docs / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n")


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_missing_required_page(tmp_path: Path) -> None:
    """Navigation validation reports alpha-critical pages missing from docs."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "mkdocs.yml").write_text(
        "nav:\n  - Home: index.md\n  - Start Here:\n      - start-here/index.md\n",
    )
    (docs / "index.md").write_text("# Home\n")

    errors = validate_docs_navigation(tmp_path)

    assert "Missing docs page: docs/start-here/index.md" in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_missing_required_nav_entry(
    tmp_path: Path,
) -> None:
    """Navigation validation reports required pages omitted from nav."""
    _write_required_docs(tmp_path)
    (tmp_path / "mkdocs.yml").write_text(
        REQUIRED_NAV.replace("  - Reference:\n      - reference/index.md\n", ""),
    )

    errors = validate_docs_navigation(tmp_path)

    assert "Missing docs nav entry: docs/reference/index.md" in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_accepts_required_alpha_pages(tmp_path: Path) -> None:
    """Navigation validation passes when alpha-critical pages exist."""
    _write_required_docs(tmp_path)
    (tmp_path / "mkdocs.yml").write_text(REQUIRED_NAV)

    assert validate_docs_navigation(tmp_path) == []


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_broken_required_doc_link(
    tmp_path: Path,
) -> None:
    """Navigation validation reports broken relative Markdown links."""
    _write_required_docs(tmp_path)
    (tmp_path / "mkdocs.yml").write_text(REQUIRED_NAV)
    (tmp_path / "docs/start-here/index.md").write_text(
        "# Start Here\n\nSee [missing](../missing.md).\n",
    )

    errors = validate_docs_navigation(tmp_path)

    assert (
        "Broken docs link in docs/start-here/index.md: ../missing.md -> docs/missing.md"
    ) in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_accepts_valid_required_doc_link(
    tmp_path: Path,
) -> None:
    """Navigation validation accepts existing relative Markdown links."""
    _write_required_docs(tmp_path)
    (tmp_path / "mkdocs.yml").write_text(REQUIRED_NAV)
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
    (tmp_path / "mkdocs.yml").write_text(REQUIRED_NAV)
    (tmp_path / "docs/start-here/index.md").write_text(
        "# Start Here\n\nSee [placeholder]( ).\n",
    )

    assert validate_docs_navigation(tmp_path) == []
