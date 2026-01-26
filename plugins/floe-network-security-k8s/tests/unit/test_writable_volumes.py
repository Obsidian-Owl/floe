"""Unit tests for emptyDir writable volume generation.

Task: T043
Phase: 6 - Secure Container Runtime Configuration (US4)
User Story: US4 - Secure Container Runtime Configuration
Requirement: FR-062, FR-063
"""

from __future__ import annotations

import pytest


class TestWritableVolumeGeneration:
    """Unit tests for emptyDir writable volume generation (T046).

    When using readOnlyRootFilesystem, containers need emptyDir volumes
    for paths that require write access (e.g., /tmp, /home/floe).
    """

    @pytest.mark.requirement("FR-062")
    def test_generate_writable_volumes_returns_tuple(self) -> None:
        """Test that writable volume generation returns a tuple."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        result = plugin.generate_writable_volumes(["/tmp"])

        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.requirement("FR-062")
    def test_writable_volumes_returns_volumes_list(self) -> None:
        """Test that first element is a list of volumes."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, _ = plugin.generate_writable_volumes(["/tmp"])

        assert isinstance(volumes, list)

    @pytest.mark.requirement("FR-062")
    def test_writable_volumes_returns_volume_mounts_list(self) -> None:
        """Test that second element is a list of volume mounts."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        _, volume_mounts = plugin.generate_writable_volumes(["/tmp"])

        assert isinstance(volume_mounts, list)

    @pytest.mark.requirement("FR-062")
    def test_single_path_generates_one_volume(self) -> None:
        """Test that a single path generates one volume."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, volume_mounts = plugin.generate_writable_volumes(["/tmp"])

        assert len(volumes) == 1
        assert len(volume_mounts) == 1

    @pytest.mark.requirement("FR-062")
    def test_multiple_paths_generate_multiple_volumes(self) -> None:
        """Test that multiple paths generate multiple volumes."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, volume_mounts = plugin.generate_writable_volumes(["/tmp", "/home/floe"])

        assert len(volumes) == 2
        assert len(volume_mounts) == 2

    @pytest.mark.requirement("FR-062")
    def test_volume_is_empty_dir(self) -> None:
        """Test that volumes are emptyDir type."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, _ = plugin.generate_writable_volumes(["/tmp"])

        assert "emptyDir" in volumes[0]
        assert volumes[0]["emptyDir"] == {}

    @pytest.mark.requirement("FR-062")
    def test_volume_has_name(self) -> None:
        """Test that volumes have a name field."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, _ = plugin.generate_writable_volumes(["/tmp"])

        assert "name" in volumes[0]
        assert volumes[0]["name"]  # Not empty

    @pytest.mark.requirement("FR-062")
    def test_volume_mount_has_name(self) -> None:
        """Test that volume mounts reference the volume by name."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, volume_mounts = plugin.generate_writable_volumes(["/tmp"])

        assert "name" in volume_mounts[0]
        assert volume_mounts[0]["name"] == volumes[0]["name"]

    @pytest.mark.requirement("FR-062")
    def test_volume_mount_has_mount_path(self) -> None:
        """Test that volume mounts have correct mountPath."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        _, volume_mounts = plugin.generate_writable_volumes(["/tmp"])

        assert "mountPath" in volume_mounts[0]
        assert volume_mounts[0]["mountPath"] == "/tmp"


class TestVolumeNameGeneration:
    """Tests for volume name generation from paths."""

    @pytest.mark.requirement("FR-062")
    def test_tmp_path_generates_valid_name(self) -> None:
        """Test that /tmp generates a valid volume name."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, _ = plugin.generate_writable_volumes(["/tmp"])

        name = volumes[0]["name"]
        # K8s names must be lowercase alphanumeric with dashes
        assert name.replace("-", "").isalnum()
        assert name == name.lower()

    @pytest.mark.requirement("FR-062")
    def test_nested_path_generates_valid_name(self) -> None:
        """Test that nested paths generate valid volume names."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, _ = plugin.generate_writable_volumes(["/home/floe"])

        name = volumes[0]["name"]
        # K8s names must be lowercase alphanumeric with dashes
        assert name.replace("-", "").isalnum()
        assert name == name.lower()

    @pytest.mark.requirement("FR-062")
    def test_different_paths_generate_different_names(self) -> None:
        """Test that different paths generate different volume names."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, _ = plugin.generate_writable_volumes(["/tmp", "/home/floe"])

        names = [v["name"] for v in volumes]
        assert len(names) == len(set(names))  # All unique


class TestDefaultWritablePaths:
    """Tests for default writable paths (T047)."""

    @pytest.mark.requirement("FR-063")
    def test_tmp_path_writable(self) -> None:
        """Test that /tmp is a standard writable path."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        _, volume_mounts = plugin.generate_writable_volumes(["/tmp"])

        mount_paths = [vm["mountPath"] for vm in volume_mounts]
        assert "/tmp" in mount_paths

    @pytest.mark.requirement("FR-063")
    def test_home_floe_path_writable(self) -> None:
        """Test that /home/floe is a standard writable path."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        _, volume_mounts = plugin.generate_writable_volumes(["/home/floe"])

        mount_paths = [vm["mountPath"] for vm in volume_mounts]
        assert "/home/floe" in mount_paths

    @pytest.mark.requirement("FR-063")
    def test_empty_paths_returns_empty_lists(self) -> None:
        """Test that empty paths list returns empty volume lists."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, volume_mounts = plugin.generate_writable_volumes([])

        assert volumes == []
        assert volume_mounts == []


class TestWritableVolumesIntegration:
    """Integration tests for writable volumes with pod specs."""

    @pytest.mark.requirement("FR-062")
    def test_volumes_can_be_added_to_pod_spec(self) -> None:
        """Test that generated volumes can be added to a pod spec."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, volume_mounts = plugin.generate_writable_volumes(["/tmp", "/home/floe"])

        # Simulate adding to a pod spec
        pod_spec = {
            "volumes": volumes,
            "containers": [
                {
                    "name": "main",
                    "volumeMounts": volume_mounts,
                }
            ],
        }

        # Verify structure
        assert len(pod_spec["volumes"]) == 2
        assert len(pod_spec["containers"][0]["volumeMounts"]) == 2

    @pytest.mark.requirement("FR-062")
    def test_volume_names_match_volume_mounts(self) -> None:
        """Test that all volume mount names have matching volumes."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, volume_mounts = plugin.generate_writable_volumes(["/tmp", "/home/floe"])

        volume_names = {v["name"] for v in volumes}
        mount_names = {vm["name"] for vm in volume_mounts}

        assert volume_names == mount_names


class TestWritableVolumesNegativePaths:
    """Negative path tests for writable volume generation (L-002)."""

    @pytest.mark.requirement("FR-062")
    def test_blocked_path_proc_raises(self) -> None:
        """Test that /proc mount raises ValueError."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        with pytest.raises(ValueError, match="Mount path blocked"):
            plugin.generate_writable_volumes(["/proc"])

    @pytest.mark.requirement("FR-062")
    def test_blocked_path_sys_raises(self) -> None:
        """Test that /sys mount raises ValueError."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        with pytest.raises(ValueError, match="Mount path blocked"):
            plugin.generate_writable_volumes(["/sys"])

    @pytest.mark.requirement("FR-062")
    def test_blocked_path_dev_raises(self) -> None:
        """Test that /dev mount raises ValueError."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        with pytest.raises(ValueError, match="Mount path blocked"):
            plugin.generate_writable_volumes(["/dev"])

    @pytest.mark.requirement("FR-062")
    def test_blocked_path_etc_raises(self) -> None:
        """Test that /etc mount raises ValueError."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        with pytest.raises(ValueError, match="Mount path blocked"):
            plugin.generate_writable_volumes(["/etc"])

    @pytest.mark.requirement("FR-062")
    def test_blocked_path_var_run_raises(self) -> None:
        """Test that /var/run mount raises ValueError."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        with pytest.raises(ValueError, match="Mount path blocked"):
            plugin.generate_writable_volumes(["/var/run"])

    @pytest.mark.requirement("FR-062")
    def test_blocked_path_docker_socket_raises(self) -> None:
        """Test that docker socket mount raises ValueError."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        with pytest.raises(ValueError, match="Mount path blocked"):
            plugin.generate_writable_volumes(["/var/run/docker.sock"])

    @pytest.mark.requirement("FR-062")
    def test_blocked_path_run_raises(self) -> None:
        """Test that /run mount raises ValueError."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        with pytest.raises(ValueError, match="Mount path blocked"):
            plugin.generate_writable_volumes(["/run"])

    @pytest.mark.requirement("FR-062")
    def test_blocked_path_root_raises(self) -> None:
        """Test that root filesystem mount raises ValueError."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        with pytest.raises(ValueError, match="Mount path blocked"):
            plugin.generate_writable_volumes(["/"])

    @pytest.mark.requirement("FR-062")
    def test_blocked_path_in_list_raises(self) -> None:
        """Test that blocked path in list with valid paths raises ValueError."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        with pytest.raises(ValueError, match="Mount path blocked"):
            plugin.generate_writable_volumes(["/tmp", "/proc", "/home/floe"])
