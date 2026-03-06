"""Kind cluster configuration tests.

Validates that kind-config.yaml has the expected port mappings
for localhost access to NodePort services.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

KIND_CONFIG_PATH = (
    Path(__file__).parent.parent.parent.parent / "testing" / "k8s" / "kind-config.yaml"
)


class TestKindConfig:
    """Tests for Kind cluster configuration."""

    @pytest.mark.requirement("AC-29.2")
    def test_port_mapping_count(self) -> None:
        """Kind config has expected number of port mappings."""
        config = yaml.safe_load(KIND_CONFIG_PATH.read_text())
        mappings = config["nodes"][0]["extraPortMappings"]
        assert len(mappings) == 15, f"Expected 15 port mappings, got {len(mappings)}"

    @pytest.mark.requirement("AC-29.2")
    def test_key_port_mappings_exist(self) -> None:
        """Kind config includes critical NodePort mappings."""
        config = yaml.safe_load(KIND_CONFIG_PATH.read_text())
        mappings = config["nodes"][0]["extraPortMappings"]
        container_ports = {m["containerPort"] for m in mappings}
        expected = {30181, 30182, 30050, 30051, 30418}
        missing = expected - container_ports
        assert not missing, f"Missing port mappings for container ports: {missing}"
