from __future__ import annotations

from floe_core.telemetry.lifecycle import plugin_lifecycle_attributes


def test_plugin_lifecycle_attributes_are_secret_free() -> None:
    attrs = plugin_lifecycle_attributes(
        plugin_type="SECRETS",
        plugin_name="k8s",
        plugin_version="0.1.0",
        floe_api_version="0.1",
        phase="health_check",
        status="unhealthy",
        error_type="SecretBackendUnavailableError",
        extra={"token": "must-not-leak", "backend": "kubernetes"},
    )

    assert attrs["floe.plugin.type"] == "SECRETS"
    assert attrs["floe.plugin.name"] == "k8s"
    assert attrs["floe.plugin.version"] == "0.1.0"
    assert attrs["floe.plugin.floe_api_version"] == "0.1"
    assert attrs["floe.plugin.lifecycle.phase"] == "health_check"
    assert attrs["floe.plugin.lifecycle.status"] == "unhealthy"
    assert attrs["floe.error.type"] == "SecretBackendUnavailableError"
    assert attrs["backend"] == "kubernetes"
    assert "token" not in attrs
