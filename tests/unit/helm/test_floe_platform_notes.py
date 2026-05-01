"""Unit-level checks for floe-platform Helm NOTES output."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CHART_PATH = _REPO_ROOT / "charts" / "floe-platform"
_NOTES_PATH = _REPO_ROOT / "charts" / "floe-platform" / "templates" / "NOTES.txt"
_SITE_CONFIG_PATH = _REPO_ROOT / "docs-site" / "site-config.mjs"


def _canonical_docs_site() -> str:
    """Read the canonical docs URL from docs-site configuration."""
    match = re.search(
        r"export const docsSite = '([^']+)';",
        _SITE_CONFIG_PATH.read_text(),
    )
    assert match is not None, "docs-site/site-config.mjs must export docsSite"
    return match.group(1)


def _render_notes(*extra_args: str) -> str:
    """Render Helm install output including NOTES."""
    with tempfile.TemporaryDirectory() as temp_dir:
        chart_path = Path(temp_dir) / "floe-platform"
        # NOTES rendering should stay hermetic; external subcharts are validated
        # in Helm-specific CI lanes after dependency build.
        shutil.copytree(
            _CHART_PATH,
            chart_path,
            ignore=shutil.ignore_patterns("charts", "Chart.lock"),
        )

        chart_yaml_path = chart_path / "Chart.yaml"
        chart_yaml = yaml.safe_load(chart_yaml_path.read_text())
        chart_yaml["dependencies"] = []
        chart_yaml_path.write_text(yaml.safe_dump(chart_yaml, sort_keys=False))

        notes_fixture_path = chart_path / "files" / "NOTES.txt"
        notes_fixture_path.parent.mkdir()
        notes_fixture_path.write_text((chart_path / "templates" / "NOTES.txt").read_text())

        notes_wrapper_path = chart_path / "templates" / "rendered-notes-test.yaml"
        notes_wrapper_path.write_text(
            """apiVersion: v1
kind: ConfigMap
metadata:
  name: rendered-notes-test
data:
  notes: |-
{{ tpl (.Files.Get "files/NOTES.txt") . | nindent 4 }}
"""
        )

        result = subprocess.run(
            [
                "helm",
                "template",
                "floe",
                str(chart_path),
                "--debug",
                "--show-only",
                "templates/rendered-notes-test.yaml",
                *extra_args,
            ],
            cwd=_REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "helm template failed while rendering NOTES fixture\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )

        rendered_docs = yaml.safe_load_all(result.stdout)
        for rendered_doc in rendered_docs:
            if (
                isinstance(rendered_doc, dict)
                and rendered_doc.get("kind") == "ConfigMap"
                and rendered_doc.get("metadata", {}).get("name") == "rendered-notes-test"
            ):
                return str(rendered_doc["data"]["notes"])

        raise AssertionError(
            "rendered-notes-test ConfigMap not found in Helm output\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )


@pytest.mark.requirement("alpha-docs")
def test_notes_docs_links_use_current_starlight_routes() -> None:
    """Helm NOTES must not emit stale public docs URLs."""
    content = _NOTES_PATH.read_text()
    docs_site = _canonical_docs_site()

    assert "floe.dev" not in content
    assert "/docs/deployment/helm" not in content
    assert "/docs/troubleshooting" not in content
    assert f"{docs_site}/" in content
    assert f"{docs_site}/guides/deployment/kubernetes-helm" in content
    assert f"{docs_site}/contributing/troubleshooting" in content


@pytest.mark.requirement("alpha-docs")
def test_rendered_notes_keep_troubleshooting_numbering_on_new_lines() -> None:
    """Rendered Helm NOTES must keep troubleshooting items separated from headings."""
    rendered_notes = _render_notes()
    docs_site = _canonical_docs_site()

    assert "issues:1." not in rendered_notes
    assert "issues:3." not in rendered_notes
    assert "check these common issues:\n\n1. Schema validation error" in rendered_notes
    assert f"{docs_site}/guides/deployment/kubernetes-helm" in rendered_notes


@pytest.mark.requirement("alpha-docs")
def test_rendered_notes_use_valid_helm_template_chart_reference_examples() -> None:
    """Rendered Helm NOTES must not suggest the chart name as a repo-root path."""
    rendered_notes = _render_notes()

    assert "helm template test floe-platform" not in rendered_notes
    assert (
        "helm template test <chart-reference> -n default -f your-values.yaml --debug"
        in rendered_notes
    )
    assert (
        "helm template test ./charts/floe-platform -n default -f your-values.yaml --debug"
        in rendered_notes
    )
    assert "helm template test floe/floe-platform" not in rendered_notes
    assert (
        "helm template test <published-chart-reference> -n default -f your-values.yaml --debug"
        in rendered_notes
    )


@pytest.mark.requirement("alpha-docs")
def test_rendered_notes_namespace_scope_troubleshooting_pod_commands() -> None:
    """Rendered Helm NOTES troubleshooting commands must include the release namespace."""
    rendered_notes = _render_notes(
        "--set",
        "polaris.bootstrap.enabled=true",
        "--set",
        "polaris.auth.bootstrapCredentials.clientSecret=test-secret",
        "--set",
        "minio.enabled=true",
    )

    assert "kubectl get pods -n default -l app.kubernetes.io/component=minio" in rendered_notes
    assert "kubectl get pods -n default -l app.kubernetes.io/component=polaris" in rendered_notes
    assert "kubectl get pods -l app.kubernetes.io/component=minio)" not in rendered_notes
    assert "kubectl get pods -l app.kubernetes.io/component=polaris)" not in rendered_notes


@pytest.mark.requirement("alpha-docs")
def test_rendered_notes_use_canonical_otel_service_name() -> None:
    """Rendered Helm NOTES must advertise the canonical OTel service name."""
    rendered_notes = _render_notes()

    assert "OTLP gRPC endpoint: floe-platform-otel:4317" in rendered_notes
    assert "OTLP HTTP endpoint: http://floe-platform-otel:4318" in rendered_notes
    assert "floe-platform-otel-collector" not in rendered_notes
    assert "floe-otel" not in rendered_notes
