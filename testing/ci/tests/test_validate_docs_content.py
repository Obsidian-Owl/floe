"""Tests for semantic documentation content validation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = ROOT / "testing" / "ci" / "validate-docs-content.py"


def load_validator() -> ModuleType:
    """Load the hyphenated validator script as a test module."""
    spec = importlib.util.spec_from_file_location("validate_docs_content_script", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.requirement("alpha-docs")
def test_rejects_stale_release_patch_claim(tmp_path: Path) -> None:
    """Content validation rejects stale release evidence claims in public docs."""
    docs = tmp_path / "docs" / "releases"
    docs.mkdir(parents=True)
    (docs / "v0.1.0-alpha.1-checklist.md").write_text(
        "# Release\nCustomer 360 passed on an unmerged release-hardening patch.\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("unmerged release-hardening patch" in error for error in errors)
    assert any("docs/releases/v0.1.0-alpha.1-checklist.md:2" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_rejects_internal_agent_runbook_in_public_reference(tmp_path: Path) -> None:
    """Content validation rejects internal agent runbook language in public docs."""
    docs = tmp_path / "docs" / "reference"
    docs.mkdir(parents=True)
    (docs / "cube-skill.md").write_text(
        "---\nname: cube-semantic-layer\n---\n"
        "ALWAYS USE when building semantic layer.\n"
        "When this skill is invoked, you should verify runtime state.\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("internal agent runbook phrase" in error for error in errors)
    assert any("ALWAYS USE when" in error for error in errors)
    assert any("When this skill is invoked" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_rejects_unsupported_public_cli_schema_export(tmp_path: Path) -> None:
    """Content validation rejects public snippets for CLI commands that do not exist."""
    docs = tmp_path / "docs" / "reference"
    docs.mkdir(parents=True)
    (docs / "floe-yaml-schema.md").write_text(
        "# Schema\n\n```bash\nfloe schema export --format json\n```\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("unsupported CLI command 'floe schema export'" in error for error in errors)
    assert any("docs/reference/floe-yaml-schema.md:4" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_rejects_uncaveated_data_mesh_migration_claims(tmp_path: Path) -> None:
    """Content validation rejects alpha-overstated Data Mesh migration language."""
    docs = tmp_path / "docs" / "architecture"
    docs.mkdir(parents=True)
    (docs / "summary.md").write_text(
        "# Architecture\n\nScale to Data Mesh seamlessly without rewrites.\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any(
        "uncaveated Data Mesh migration language 'without rewrites'" in error for error in errors
    )
    assert any(
        "uncaveated Data Mesh migration language 'Data Mesh seamlessly'" in error
        for error in errors
    )


@pytest.mark.requirement("alpha-docs")
def test_rejects_docker_compose_and_floe_dev_product_paths(tmp_path: Path) -> None:
    """Content validation rejects stale local product paths in public docs."""
    docs = tmp_path / "docs" / "guides" / "deployment"
    docs.mkdir(parents=True)
    (docs / "local-development.md").write_text(
        "# Local\n\n"
        "Use Docker Compose setup for evaluation.\n"
        "Run `docker compose up`.\n"
        "Run `floe dev`.\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("Docker Compose setup presented as a product path" in error for error in errors)
    assert any("'docker compose up' presented as a product path" in error for error in errors)
    assert any("unsupported CLI command 'floe dev'" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_allows_negative_or_planned_docker_compose_and_floe_dev_context(tmp_path: Path) -> None:
    """Content validation permits negative and planned references to stale paths."""
    docs = tmp_path / "docs" / "guides" / "deployment"
    docs.mkdir(parents=True)
    (docs / "local-development.md").write_text(
        "# Local\n\n"
        "Docker Compose is not supported for Floe product evaluation.\n"
        "`floe dev` is planned and not implemented.\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert errors == []


@pytest.mark.requirement("alpha-docs")
def test_allows_unsupported_cli_snippet_in_excluded_docs(tmp_path: Path) -> None:
    """Content validation ignores unsupported snippets in docs excluded from publication."""
    docs_site = tmp_path / "docs-site"
    docs_site.mkdir()
    (docs_site / "docs-manifest.json").write_text(
        json.dumps(
            {
                "includePrefixes": ["docs/"],
                "excludePrefixes": ["docs/internal/"],
                "sections": [],
            }
        )
    )
    docs = tmp_path / "docs" / "internal"
    docs.mkdir(parents=True)
    (docs / "planned.md").write_text("Planned: `floe schema export --format json`.\n")

    assert load_validator().validate_docs_content(tmp_path) == []


@pytest.mark.requirement("alpha-docs")
def test_rejects_wrong_plugin_count(tmp_path: Path) -> None:
    """Content validation rejects plugin category counts that drift from code."""
    readme = tmp_path / "README.md"
    readme.write_text("Floe lets teams choose from 12 plugin types.\n")

    errors = load_validator().validate_docs_content(tmp_path, plugin_category_count=14)

    assert any("plugin count" in error for error in errors)
    assert any("expected 14 plugin categories" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_allows_historical_adr_version_or_history_sections(tmp_path: Path) -> None:
    """Content validation permits historical plugin counts in ADR history sections."""
    adr = tmp_path / "docs" / "architecture" / "adr" / "0043-dbt-runtime-abstraction.md"
    adr.parent.mkdir(parents=True)
    adr.write_text(
        "# ADR\n\n"
        "## Version History\n\n"
        "Earlier versions described DBTPlugin as the 12th plugin type.\n"
    )

    errors = load_validator().validate_docs_content(tmp_path, plugin_category_count=14)

    assert errors == []


@pytest.mark.requirement("alpha-docs")
def test_uses_manifest_include_and_exclude_prefixes_when_present(tmp_path: Path) -> None:
    """Content validation follows docs manifest include and exclude publication scope."""
    docs_site = tmp_path / "docs-site"
    docs_site.mkdir()
    (docs_site / "docs-manifest.json").write_text(
        json.dumps(
            {
                "includePrefixes": ["docs/public/"],
                "excludePrefixes": ["docs/internal/"],
                "sections": [
                    {
                        "label": "Docs",
                        "items": [
                            {
                                "title": "Home",
                                "source": "docs/index.md",
                                "slug": "index",
                            }
                        ],
                    }
                ],
            }
        )
    )
    (tmp_path / "docs/public").mkdir(parents=True)
    (tmp_path / "docs/internal/agent-skills").mkdir(parents=True)
    (tmp_path / "docs/index.md").write_text("# Home\n")
    (tmp_path / "docs/public/current.md").write_text("Floe has 12 plugin types.\n")
    (tmp_path / "docs/internal/agent-skills/private.md").write_text(
        "ALWAYS USE when working on private agent runbooks.\n"
    )
    (tmp_path / "docs/superpowers.md").write_text(
        "This plan quoted an unmerged release-hardening patch.\n"
    )

    errors = load_validator().validate_docs_content(tmp_path, plugin_category_count=14)

    assert any("docs/public/current.md:1" in error for error in errors)
    assert not any("docs/internal/agent-skills/private.md" in error for error in errors)
    assert not any("docs/superpowers.md" in error for error in errors)
