"""Static contract tests for Dagster webserver port wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from testing.fixtures.services import SERVICE_DEFAULT_PORTS

VALUES_BASE = Path("charts/floe-platform/values.yaml")
VALUES_TEST = Path("charts/floe-platform/values-test.yaml")


def _load_values(path: Path) -> dict[str, Any]:
    """Load one Helm values file."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.requirement("env-resilient-AC-1")
def test_base_values_match_dagster_webserver_service_contract() -> None:
    """Base floe-platform values must use the shared Dagster webserver port."""
    values = _load_values(VALUES_BASE)
    webserver = values["dagster"]["dagsterWebserver"]

    assert webserver["service"]["port"] == SERVICE_DEFAULT_PORTS["dagster-webserver"] == 3000
    assert webserver["readinessProbe"]["httpGet"]["port"] == 3000


@pytest.mark.requirement("env-resilient-AC-1")
def test_test_values_keep_dagster_webserver_probe_aligned() -> None:
    """The test overlay must not drift from the Dagster webserver port contract."""
    values = _load_values(VALUES_TEST)
    webserver = values["dagster"]["dagsterWebserver"]

    assert webserver["service"]["port"] == SERVICE_DEFAULT_PORTS["dagster-webserver"] == 3000
    assert webserver["readinessProbe"]["httpGet"]["port"] == 3000
