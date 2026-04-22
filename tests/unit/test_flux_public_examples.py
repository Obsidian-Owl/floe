"""Structural tests for the public Flux examples and operator docs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FLUX_DIR = _REPO_ROOT / "charts" / "examples" / "flux"
_OCI_REPOSITORY_PATH = _FLUX_DIR / "ocirepository.yaml"
_HELMRELEASE_PATH = _FLUX_DIR / "helmrelease.yaml"
_KUSTOMIZATION_PATH = _FLUX_DIR / "kustomization.yaml"
_README_PATH = _REPO_ROOT / "charts" / "floe-platform" / "README.md"
_GUIDE_PATH = _REPO_ROOT / "docs" / "guides" / "deployment" / "gitops-flux.md"
_PUBLIC_STORY_PATHS = (
    _OCI_REPOSITORY_PATH,
    _HELMRELEASE_PATH,
    _KUSTOMIZATION_PATH,
    _README_PATH,
    _GUIDE_PATH,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a single-document YAML file."""
    assert path.exists(), f"File not found: {path}"
    docs = list(yaml.safe_load_all(path.read_text()))
    assert len(docs) == 1, f"Expected one YAML document in {path}, got {len(docs)}"
    return docs[0]


def _section(markdown_path: Path, heading: str) -> str:
    """Extract a markdown section body by heading."""
    content = markdown_path.read_text()
    marker = f"## {heading}\n"
    start = content.index(marker) + len(marker)
    remainder = content[start:]
    next_heading = remainder.find("\n## ")
    if next_heading == -1:
        return remainder.strip()
    return remainder[:next_heading].strip()


@pytest.mark.requirement("AC-1")
def test_public_flux_examples_include_ocirepository() -> None:
    """The public example set includes a first-class OCIRepository source."""
    doc = _load_yaml(_OCI_REPOSITORY_PATH)

    assert doc["apiVersion"] == "source.toolkit.fluxcd.io/v1"
    assert doc["kind"] == "OCIRepository"
    assert doc["metadata"]["name"] == "floe-platform"
    assert doc["metadata"]["namespace"] == "flux-system"
    assert doc["spec"]["url"] == "oci://ghcr.io/obsidian-owl/charts/floe-platform"
    assert "ref" in doc["spec"], "OCIRepository should expose an explicit chart version knob"


@pytest.mark.requirement("AC-2")
def test_public_helmrelease_uses_ga_api_oci_source_and_values_from() -> None:
    """The public HelmRelease points at OCIRepository and external values data."""
    doc = _load_yaml(_HELMRELEASE_PATH)

    assert doc["apiVersion"] == "helm.toolkit.fluxcd.io/v2"
    assert doc["kind"] == "HelmRelease"
    assert "chartRef" in doc["spec"]
    assert "chart" not in doc["spec"], "OCI-based public example should use chartRef"

    chart_ref = doc["spec"]["chartRef"]
    assert chart_ref["kind"] == "OCIRepository"
    assert chart_ref["name"] == "floe-platform"
    assert chart_ref["namespace"] == "flux-system"

    values_from = doc["spec"]["valuesFrom"]
    assert [entry["kind"] for entry in values_from] == ["ConfigMap", "Secret"]
    assert values_from[0]["name"] == "floe-compiled-values"
    assert values_from[0]["valuesKey"] == "values.yaml"
    assert values_from[1]["name"] == "floe-platform-overrides"
    assert values_from[1]["valuesKey"] == "values.yaml"


@pytest.mark.requirement("AC-3")
def test_public_kustomization_documents_gitops_layout_and_secret_strategies() -> None:
    """The public Kustomization keeps GitRepository orchestration and explains the layout."""
    doc = _load_yaml(_KUSTOMIZATION_PATH)
    content = _KUSTOMIZATION_PATH.read_text()

    assert doc["apiVersion"] == "kustomize.toolkit.fluxcd.io/v1"
    assert doc["kind"] == "Kustomization"
    assert doc["spec"]["sourceRef"]["kind"] == "GitRepository"
    assert doc["spec"]["sourceRef"]["name"] == "floe-config"
    assert doc["spec"]["path"] == "./clusters/dev/floe-platform"
    assert "compiled-values-configmap.yaml" in content
    assert "Age/SOPS" in content
    assert "External Secrets Operator" in content


@pytest.mark.requirement("AC-4")
def test_chart_readme_flux_section_is_pointer_only() -> None:
    """The chart README points operators at the public examples and guide."""
    section = _section(_README_PATH, "GitOps Deployment")

    assert "charts/examples/flux/" in section
    assert "docs/guides/deployment/gitops-flux.md" in section
    assert "charts/floe-platform/flux" not in section
    assert "HelmRepository" not in section


@pytest.mark.requirement("AC-5")
def test_gitops_flux_guide_exposes_user_facing_knobs() -> None:
    """The dedicated guide documents the public ConfigMap and chart controls."""
    content = _GUIDE_PATH.read_text()

    assert "--output-format configmap" in content
    assert "--configmap-name" in content
    assert "floe-compiled-values" in content
    assert "--namespace" in content
    assert "same namespace as the HelmRelease" in content
    assert "flux-system" in content
    assert "oci://ghcr.io/obsidian-owl/charts/floe-platform" in content
    assert "ref.tag" in content or "ref.semver" in content
    assert "valuesFrom" in content
    assert "ConfigMap" in content
    assert "Secret" in content


@pytest.mark.requirement("AC-6")
def test_public_flux_story_does_not_regress_to_legacy_paths_or_api_versions() -> None:
    """The public docs and examples stay off the old public story."""
    legacy_terms = (
        "HelmRepository",
        "helm.toolkit.fluxcd.io/v2beta2",
        "charts/floe-platform/flux",
    )

    for path in _PUBLIC_STORY_PATHS:
        assert path.exists(), f"Expected public story file to exist: {path}"
        content = path.read_text()
        for term in legacy_terms:
            assert term not in content, f"Unexpected legacy term {term!r} in {path}"
