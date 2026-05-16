from __future__ import annotations

from pathlib import Path

from floe_core.plugin_types import PluginType

ROOT = Path(__file__).resolve().parents[2]


def test_network_security_entry_point_has_explicit_registry_decision() -> None:
    pyproject = ROOT / "plugins" / "floe-network-security-k8s" / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")

    assert '[project.entry-points."floe.network_security"]' in text
    assert (
        hasattr(PluginType, "NETWORK_SECURITY")
        or "network_security is documented as a non-PluginType extension" in text
    )


def test_alpha_plugin_types_have_observability_categories() -> None:
    expected = {
        "COMPUTE",
        "ORCHESTRATOR",
        "CATALOG",
        "STORAGE",
        "TELEMETRY_BACKEND",
        "LINEAGE_BACKEND",
        "DBT",
        "SEMANTIC_LAYER",
        "INGESTION",
        "SECRETS",
        "IDENTITY",
        "QUALITY",
        "RBAC",
        "ALERT_CHANNEL",
    }

    assert expected.issubset({member.name for member in PluginType})
