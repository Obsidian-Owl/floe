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
def test_rejects_stale_chart_metadata(tmp_path: Path) -> None:
    """Content validation rejects chart metadata that contradicts alpha scope."""
    chart = tmp_path / "charts" / "floe-platform" / "Chart.yaml"
    chart.parent.mkdir(parents=True)
    chart.write_text(
        "apiVersion: v2\n"
        "name: floe-platform\n"
        "description: Production-ready data platform\n"
        'appVersion: "1.0.0"\n'
        "home: https://github.com/Obsidian-Owl/floe-runtime\n"
        "sources:\n"
        "  - https://github.com/Obsidian-Owl/floe-runtime/tree/main/charts/floe-platform\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("must not claim production-ready status" in error for error in errors)
    assert any("stale appVersion 1.0.0" in error for error in errors)
    assert any("must match alpha release" in error for error in errors)
    assert any("not floe-runtime" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_rejects_unsupported_lifecycle_commands_in_user_facing_docs(tmp_path: Path) -> None:
    """Content validation rejects planned lifecycle commands as executable alpha paths."""
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Floe\n\n"
        "```bash\n"
        "$ floe init --platform=v1.0.0\n"
        "$ floe validate\n"
        "$ floe compile\n"
        "$ floe run\n"
        "$ floe test\n"
        "$ floe platform test\n"
        "```\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("'floe init' is not a supported current alpha workflow" in error for error in errors)
    assert any(
        "'floe validate' is not a supported current alpha workflow" in error for error in errors
    )
    assert any(
        "'floe compile' is not a supported current alpha workflow" in error for error in errors
    )
    assert any("'floe run' is not a supported current alpha workflow" in error for error in errors)
    assert any("'floe test' is not a supported current alpha workflow" in error for error in errors)
    assert any(
        "'floe platform test' is not a supported current alpha workflow" in error
        for error in errors
    )
    assert any("README.md:4" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_allows_platform_compile_and_demo_compile_paths(tmp_path: Path) -> None:
    """Content validation allows current alpha compile commands."""
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Floe\n\n```bash\nmake compile-demo\nuv run floe platform compile\n```\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert errors == []


@pytest.mark.requirement("alpha-docs")
def test_allows_root_floe_compile_when_marked_planned(tmp_path: Path) -> None:
    """Content validation permits root command references when explicitly planned/stubbed."""
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Floe\n\n"
        "The planned root data-team commands are not yet implemented: "
        "`floe validate` and `floe compile`.\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert errors == []


@pytest.mark.requirement("alpha-docs")
def test_rejects_unsupported_lifecycle_commands_with_bare_target_artifact_context(
    tmp_path: Path,
) -> None:
    """Target artifact wording does not caveat unsupported lifecycle commands."""
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Floe\n\n"
        "Run the compiled target artifact with `floe run target/compiled_artifacts.json`.\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("'floe run' is not a supported current alpha workflow" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_rejects_lifecycle_commands_in_contributor_docs_without_caveat(
    tmp_path: Path,
) -> None:
    """Content validation covers contributor docs because they are public docs."""
    docs_site = tmp_path / "docs-site"
    docs_site.mkdir()
    (docs_site / "docs-manifest.json").write_text(
        json.dumps(
            {
                "includePrefixes": ["docs/contributing/"],
                "excludePrefixes": [],
                "sections": [],
            }
        )
    )
    contributing = tmp_path / "docs" / "contributing"
    contributing.mkdir(parents=True)
    (contributing / "testing.md").write_text("# Testing\n\n```bash\nfloe compile\n```\n")

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("docs/contributing/testing.md:4" in error for error in errors)
    assert any(
        "'floe compile' is not a supported current alpha workflow" in error for error in errors
    )


@pytest.mark.requirement("alpha-docs")
def test_rejects_contract_and_architecture_lifecycle_examples_without_caveat(
    tmp_path: Path,
) -> None:
    """Content validation covers published contracts and non-ADR architecture docs."""
    contracts = tmp_path / "docs" / "contracts"
    architecture = tmp_path / "docs" / "architecture"
    contracts.mkdir(parents=True)
    architecture.mkdir(parents=True)
    (contracts / "index.md").write_text("# Contracts\n\n```bash\nfloe compile\n```\n")
    (architecture / "four-layer-overview.md").write_text(
        "# Four Layers\n\n```bash\nfloe platform test\n```\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("docs/contracts/index.md:4" in error for error in errors)
    assert any("docs/architecture/four-layer-overview.md:4" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_rejects_vague_customer_360_run_handoff(tmp_path: Path) -> None:
    """Content validation requires the concrete alpha Customer 360 run path."""
    docs = tmp_path / "docs" / "data-engineers"
    docs.mkdir(parents=True)
    (docs / "first-data-product.md").write_text(
        "# First Data Product\n\n"
        "Use the run command or deployment command documented by your Platform Engineer.\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("vague Customer 360 run/deploy handoff" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_rejects_uncaveated_data_mesh_discovery_commands(tmp_path: Path) -> None:
    """Content validation rejects Data Mesh discovery commands as current alpha workflows."""
    docs = tmp_path / "docs" / "architecture"
    docs.mkdir(parents=True)
    (docs / "mesh.md").write_text("# Mesh\n\n```bash\nfloe products list\n```\n")

    errors = load_validator().validate_docs_content(tmp_path)

    assert any(
        "Data Mesh discovery CLI command is not a supported current alpha" in error
        for error in errors
    )


@pytest.mark.requirement("alpha-docs")
def test_allows_target_state_data_mesh_discovery_commands(tmp_path: Path) -> None:
    """Content validation permits explicitly target-state Data Mesh discovery commands."""
    docs = tmp_path / "docs" / "architecture" / "adr"
    docs.mkdir(parents=True)
    (docs / "0021-data-architecture-patterns.md").write_text(
        "# ADR\n\n"
        "## Target-State Data Mesh Discovery\n\n"
        "```bash\n"
        "# List all products\n"
        "floe products list\n"
        "```\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert errors == []


@pytest.mark.requirement("alpha-docs")
def test_rejects_dagster_daemon_mode_as_current_chart_contract(tmp_path: Path) -> None:
    """Content validation rejects unsupported daemon.mode production claims."""
    docs = tmp_path / "docs" / "guides" / "deployment"
    docs.mkdir(parents=True)
    (docs / "production.md").write_text(
        "# Production\n\n```yaml\ndaemon:\n  mode: ha\n```\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert any("Dagster daemon HA mode contract is not implemented" in error for error in errors)


@pytest.mark.requirement("alpha-docs")
def test_allows_dagster_daemon_ha_when_marked_candidate(tmp_path: Path) -> None:
    """Content validation permits daemon HA examples when clearly candidate-only."""
    docs = tmp_path / "docs" / "guides" / "deployment"
    docs.mkdir(parents=True)
    (docs / "production.md").write_text(
        "# Production\n\n## Future Candidate Pattern\n\n```yaml\ndaemon:\n  mode: ha\n```\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert errors == []


@pytest.mark.requirement("alpha-docs")
def test_allows_adr_lifecycle_commands_as_historical_or_target_context(tmp_path: Path) -> None:
    """Content validation does not force broad rewrites of ADR command references."""
    adr = tmp_path / "docs" / "architecture" / "adr" / "0001-target.md"
    adr.parent.mkdir(parents=True)
    adr.write_text("# ADR\n\n```bash\nfloe compile\nfloe run\n```\n")

    errors = load_validator().validate_docs_content(tmp_path)

    assert errors == []


@pytest.mark.requirement("alpha-docs")
def test_accepts_alpha_chart_metadata(tmp_path: Path) -> None:
    """Content validation accepts alpha-scoped floe-platform metadata."""
    chart = tmp_path / "charts" / "floe-platform" / "Chart.yaml"
    chart.parent.mkdir(parents=True)
    chart.write_text(
        "apiVersion: v2\n"
        "name: floe-platform\n"
        "description: Alpha data platform chart for local/dev Floe validation\n"
        'appVersion: "0.1.0-alpha.1"\n'
        "home: https://github.com/Obsidian-Owl/floe\n"
        "sources:\n"
        "  - https://github.com/Obsidian-Owl/floe/tree/main/charts/floe-platform\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    assert errors == []


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
def test_reports_one_docker_compose_development_path_error_per_line(tmp_path: Path) -> None:
    """Content validation reports the bidirectional Docker Compose path rule once."""
    docs = tmp_path / "docs" / "guides" / "deployment"
    docs.mkdir(parents=True)
    (docs / "local-development.md").write_text(
        "# Local\n\n"
        "Docker Compose development workflows make evaluation Docker Compose friendly.\n",
    )

    errors = load_validator().validate_docs_content(tmp_path)

    matching_errors = [
        error
        for error in errors
        if "Docker Compose presented as a development or evaluation product path" in error
    ]
    assert len(matching_errors) == 1


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
    readme.write_text(
        "Floe lets teams choose from 12 plugin types.\n"
        "The plugin-quality agent covers 11 floe plugin types testing.\n"
        "The architecture page mentions 11 plugin interfaces.\n",
    )

    errors = load_validator().validate_docs_content(tmp_path, plugin_category_count=14)

    assert any("plugin count" in error for error in errors)
    assert any("expected 14 plugin categories" in error for error in errors)
    assert any("plugin count 11" in error for error in errors)


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
