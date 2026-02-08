"""Unit tests for writable volume mounts with readOnlyRootFilesystem.

Tests the configurable volume mount support for writable directories
when using readOnlyRootFilesystem: true per Pod Security Standards.

Task: T055
User Story: US5 - Pod Security Standards
Requirements: FR-043
"""

from __future__ import annotations

import pytest


class TestWritableVolumeMountConfig:
    """Unit tests for WritableVolumeMount configuration."""

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_default_paths(self) -> None:
        """Test default writable volume mounts include common paths (FR-043)."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()

        # Default should include common writable directories
        assert config.writable_volume_mounts is not None
        mount_paths = {m.mount_path for m in config.writable_volume_mounts}
        assert "/tmp" in mount_paths

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_custom_paths(self) -> None:
        """Test custom writable volume mounts can be configured (FR-043)."""
        from floe_core.schemas.rbac import PodSecurityConfig, WritableVolumeMount

        custom_mounts = [
            WritableVolumeMount(name="app-cache", mount_path="/app/cache"),
            WritableVolumeMount(name="logs", mount_path="/var/log/app"),
        ]

        config = PodSecurityConfig(writable_volume_mounts=custom_mounts)

        assert len(config.writable_volume_mounts) == 2
        paths = {m.mount_path for m in config.writable_volume_mounts}
        assert "/app/cache" in paths
        assert "/var/log/app" in paths

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_empty_list_allowed(self) -> None:
        """Test empty writable volume mounts list is valid (FR-043)."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(writable_volume_mounts=[])

        assert config.writable_volume_mounts == []

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_with_size_limit(self) -> None:
        """Test writable volume mounts support size limits (FR-043)."""
        from floe_core.schemas.rbac import PodSecurityConfig, WritableVolumeMount

        mounts = [
            WritableVolumeMount(
                name="tmp",
                mount_path="/tmp",
                size_limit="1Gi",
            ),
        ]

        config = PodSecurityConfig(writable_volume_mounts=mounts)

        assert config.writable_volume_mounts[0].size_limit == "1Gi"

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_medium_memory(self) -> None:
        """Test writable volume mounts support memory medium (FR-043)."""
        from floe_core.schemas.rbac import PodSecurityConfig, WritableVolumeMount

        mounts = [
            WritableVolumeMount(
                name="fast-tmp",
                mount_path="/tmp",
                medium="Memory",
            ),
        ]

        config = PodSecurityConfig(writable_volume_mounts=mounts)

        assert config.writable_volume_mounts[0].medium == "Memory"


class TestWritableVolumeMountValidation:
    """Unit tests for writable volume mount validation."""

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_name_required(self) -> None:
        """Test writable volume mount requires name."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import WritableVolumeMount

        with pytest.raises(ValidationError):
            WritableVolumeMount(mount_path="/tmp")  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_path_required(self) -> None:
        """Test writable volume mount requires mount_path."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import WritableVolumeMount

        with pytest.raises(ValidationError):
            WritableVolumeMount(name="tmp")  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_name_pattern(self) -> None:
        """Test writable volume mount name follows K8s naming conventions."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import WritableVolumeMount

        # Valid names
        WritableVolumeMount(name="tmp", mount_path="/tmp")
        WritableVolumeMount(name="app-cache", mount_path="/cache")
        WritableVolumeMount(name="my-vol-123", mount_path="/data")

        # Invalid names (uppercase, underscore)
        with pytest.raises(ValidationError):
            WritableVolumeMount(name="MyVolume", mount_path="/tmp")

        with pytest.raises(ValidationError):
            WritableVolumeMount(name="my_volume", mount_path="/tmp")

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_path_absolute(self) -> None:
        """Test writable volume mount path must be absolute."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import WritableVolumeMount

        # Valid absolute paths
        WritableVolumeMount(name="tmp", mount_path="/tmp")
        WritableVolumeMount(name="cache", mount_path="/var/cache")

        # Invalid relative path
        with pytest.raises(ValidationError):
            WritableVolumeMount(name="tmp", mount_path="tmp")

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_medium_values(self) -> None:
        """Test writable volume mount medium accepts valid values."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import WritableVolumeMount

        # Valid medium values
        WritableVolumeMount(name="tmp", mount_path="/tmp", medium="")
        WritableVolumeMount(name="tmp", mount_path="/tmp", medium="Memory")

        # Invalid medium value
        with pytest.raises(ValidationError):
            WritableVolumeMount(name="tmp", mount_path="/tmp", medium="Invalid")

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_path_traversal_blocked(self) -> None:
        """Test mount path rejects path traversal attempts (security hotspot fix)."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import WritableVolumeMount

        # Path traversal attempts should be blocked
        with pytest.raises(ValidationError, match="path traversal not allowed"):
            WritableVolumeMount(name="exploit", mount_path="/../etc/passwd")

        with pytest.raises(ValidationError, match="path traversal not allowed"):
            WritableVolumeMount(name="exploit", mount_path="/tmp/../etc/passwd")

        with pytest.raises(ValidationError, match="path traversal not allowed"):
            WritableVolumeMount(name="exploit", mount_path="/var/cache/..")

    @pytest.mark.requirement("FR-043")
    def test_writable_volume_mount_valid_nested_paths(self) -> None:
        """Test mount path allows valid nested paths without traversal."""
        from floe_core.schemas.rbac import WritableVolumeMount

        # Valid nested paths should work
        WritableVolumeMount(name="nested", mount_path="/var/app/cache")
        WritableVolumeMount(name="deep", mount_path="/opt/myapp/data/temp")
        WritableVolumeMount(name="dot-dir", mount_path="/var/.hidden")


class TestWritableVolumeMountsInContainerContext:
    """Unit tests for volume mounts in container security context."""

    @pytest.mark.requirement("FR-043")
    def test_volume_mounts_generated_for_container(self) -> None:
        """Test volume mounts are included in container configuration."""
        from floe_core.schemas.rbac import PodSecurityConfig, WritableVolumeMount

        mounts = [
            WritableVolumeMount(name="tmp", mount_path="/tmp"),
            WritableVolumeMount(name="cache", mount_path="/app/cache"),
        ]

        config = PodSecurityConfig(writable_volume_mounts=mounts)
        volume_mounts = config.to_volume_mounts()

        assert len(volume_mounts) == 2
        assert volume_mounts[0]["name"] == "tmp"
        assert volume_mounts[0]["mountPath"] == "/tmp"
        assert volume_mounts[1]["name"] == "cache"
        assert volume_mounts[1]["mountPath"] == "/app/cache"

    @pytest.mark.requirement("FR-043")
    def test_volumes_generated_for_pod(self) -> None:
        """Test emptyDir volumes are generated for pod spec."""
        from floe_core.schemas.rbac import PodSecurityConfig, WritableVolumeMount

        mounts = [
            WritableVolumeMount(name="tmp", mount_path="/tmp", size_limit="100Mi"),
            WritableVolumeMount(name="fast-cache", mount_path="/cache", medium="Memory"),
        ]

        config = PodSecurityConfig(writable_volume_mounts=mounts)
        volumes = config.to_volumes()

        assert len(volumes) == 2

        # First volume: default medium with size limit
        assert volumes[0]["name"] == "tmp"
        assert volumes[0]["emptyDir"]["sizeLimit"] == "100Mi"
        assert "medium" not in volumes[0]["emptyDir"] or volumes[0]["emptyDir"].get("medium") == ""

        # Second volume: memory medium
        assert volumes[1]["name"] == "fast-cache"
        assert volumes[1]["emptyDir"]["medium"] == "Memory"

    @pytest.mark.requirement("FR-043")
    def test_empty_volumes_when_no_mounts(self) -> None:
        """Test empty lists when no volume mounts configured."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(writable_volume_mounts=[])

        assert config.to_volume_mounts() == []
        assert config.to_volumes() == []


class TestWritableVolumeMountsWithReadOnlyRoot:
    """Integration tests for volume mounts with readOnlyRootFilesystem."""

    @pytest.mark.requirement("FR-043")
    def test_read_only_root_with_writable_mounts(self) -> None:
        """Test read-only root filesystem works with writable volume mounts."""
        from floe_core.schemas.rbac import PodSecurityConfig, WritableVolumeMount

        config = PodSecurityConfig(
            read_only_root_filesystem=True,
            writable_volume_mounts=[
                WritableVolumeMount(name="tmp", mount_path="/tmp"),
            ],
        )

        container_context = config.to_container_security_context()
        volume_mounts = config.to_volume_mounts()
        volumes = config.to_volumes()

        # Root filesystem is read-only
        assert container_context["readOnlyRootFilesystem"] is True

        # But /tmp is writable via emptyDir volume
        assert len(volume_mounts) == 1
        assert volume_mounts[0]["mountPath"] == "/tmp"
        assert len(volumes) == 1
        assert "emptyDir" in volumes[0]

    @pytest.mark.requirement("FR-043")
    def test_default_mounts_provide_tmp(self) -> None:
        """Test default configuration provides /tmp as writable."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()

        # Default includes /tmp for common application needs
        volume_mounts = config.to_volume_mounts()
        mount_paths = {m["mountPath"] for m in volume_mounts}

        assert "/tmp" in mount_paths


class TestWritableVolumeMountSerialization:
    """Unit tests for volume mount serialization."""

    @pytest.mark.requirement("FR-043")
    def test_volume_mount_is_serializable(self) -> None:
        """Test volume mount configuration is JSON serializable."""
        import json

        from floe_core.schemas.rbac import PodSecurityConfig, WritableVolumeMount

        config = PodSecurityConfig(
            writable_volume_mounts=[
                WritableVolumeMount(
                    name="tmp",
                    mount_path="/tmp",
                    size_limit="100Mi",
                    medium="Memory",
                ),
            ],
        )

        # Model serialization
        json_str = config.model_dump_json()
        assert "writable_volume_mounts" in json_str

        # Volume outputs are also serializable
        volumes_json = json.dumps(config.to_volumes())
        assert "emptyDir" in volumes_json

        mounts_json = json.dumps(config.to_volume_mounts())
        assert "mountPath" in mounts_json
