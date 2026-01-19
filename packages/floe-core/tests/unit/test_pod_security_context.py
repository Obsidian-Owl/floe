"""Unit tests for PodSecurityConfig.to_pod_security_context() method.

Tests the pod-level securityContext generation including runAsNonRoot,
runAsUser, runAsGroup, fsGroup, and seccompProfile.

Task: T028
User Story: US2 - Namespace Isolation
Requirements: FR-040, FR-042, FR-044
"""

from __future__ import annotations

from typing import Any

import pytest


class TestPodSecurityContextBasicStructure:
    """Unit tests for pod security context structure."""

    @pytest.mark.requirement("FR-040")
    def test_context_has_run_as_non_root(self) -> None:
        """Test pod security context includes runAsNonRoot."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert "runAsNonRoot" in context

    @pytest.mark.requirement("FR-040")
    def test_run_as_non_root_default_true(self) -> None:
        """Test runAsNonRoot defaults to True."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert context["runAsNonRoot"] is True

    @pytest.mark.requirement("FR-044")
    def test_context_has_run_as_user(self) -> None:
        """Test pod security context includes runAsUser."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert "runAsUser" in context

    @pytest.mark.requirement("FR-044")
    def test_run_as_user_default_1000(self) -> None:
        """Test runAsUser defaults to 1000."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert context["runAsUser"] == 1000

    @pytest.mark.requirement("FR-044")
    def test_context_has_run_as_group(self) -> None:
        """Test pod security context includes runAsGroup."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert "runAsGroup" in context

    @pytest.mark.requirement("FR-044")
    def test_run_as_group_default_1000(self) -> None:
        """Test runAsGroup defaults to 1000."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert context["runAsGroup"] == 1000

    @pytest.mark.requirement("FR-044")
    def test_context_has_fs_group(self) -> None:
        """Test pod security context includes fsGroup."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert "fsGroup" in context

    @pytest.mark.requirement("FR-044")
    def test_fs_group_default_1000(self) -> None:
        """Test fsGroup defaults to 1000."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert context["fsGroup"] == 1000


class TestPodSecurityContextSeccompProfile:
    """Unit tests for seccompProfile in pod security context."""

    @pytest.mark.requirement("FR-042")
    def test_context_has_seccomp_profile(self) -> None:
        """Test pod security context includes seccompProfile."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert "seccompProfile" in context

    @pytest.mark.requirement("FR-042")
    def test_seccomp_profile_has_type(self) -> None:
        """Test seccompProfile has type field."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert "type" in context["seccompProfile"]

    @pytest.mark.requirement("FR-042")
    def test_seccomp_profile_default_runtime_default(self) -> None:
        """Test seccompProfile type defaults to RuntimeDefault."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert context["seccompProfile"]["type"] == "RuntimeDefault"

    @pytest.mark.requirement("FR-042")
    def test_seccomp_profile_configurable(self) -> None:
        """Test seccompProfile type is configurable."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(seccomp_profile_type="Localhost")
        context = config.to_pod_security_context()

        assert context["seccompProfile"]["type"] == "Localhost"


class TestPodSecurityContextCustomValues:
    """Unit tests for custom values in pod security context."""

    @pytest.mark.requirement("FR-044")
    def test_custom_run_as_user(self) -> None:
        """Test custom runAsUser value."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(run_as_user=65534)
        context = config.to_pod_security_context()

        assert context["runAsUser"] == 65534

    @pytest.mark.requirement("FR-044")
    def test_custom_run_as_group(self) -> None:
        """Test custom runAsGroup value."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(run_as_group=65534)
        context = config.to_pod_security_context()

        assert context["runAsGroup"] == 65534

    @pytest.mark.requirement("FR-044")
    def test_custom_fs_group(self) -> None:
        """Test custom fsGroup value."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(fs_group=2000)
        context = config.to_pod_security_context()

        assert context["fsGroup"] == 2000

    @pytest.mark.requirement("FR-040")
    def test_run_as_non_root_configurable(self) -> None:
        """Test runAsNonRoot is configurable."""
        from floe_core.schemas.rbac import PodSecurityConfig

        # Can be explicitly set to True (normal case)
        config_true = PodSecurityConfig(run_as_non_root=True)
        context = config_true.to_pod_security_context()
        assert context["runAsNonRoot"] is True

        # Note: Setting to False would violate restricted PSS
        # but schema allows it for flexibility
        config_false = PodSecurityConfig(run_as_non_root=False)
        context = config_false.to_pod_security_context()
        assert context["runAsNonRoot"] is False


class TestPodSecurityContextFieldTypes:
    """Unit tests for pod security context field types."""

    @pytest.mark.requirement("FR-040")
    def test_run_as_non_root_is_bool(self) -> None:
        """Test runAsNonRoot is a boolean."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert isinstance(context["runAsNonRoot"], bool)

    @pytest.mark.requirement("FR-044")
    def test_run_as_user_is_int(self) -> None:
        """Test runAsUser is an integer."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert isinstance(context["runAsUser"], int)

    @pytest.mark.requirement("FR-044")
    def test_run_as_group_is_int(self) -> None:
        """Test runAsGroup is an integer."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert isinstance(context["runAsGroup"], int)

    @pytest.mark.requirement("FR-044")
    def test_fs_group_is_int(self) -> None:
        """Test fsGroup is an integer."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert isinstance(context["fsGroup"], int)

    @pytest.mark.requirement("FR-042")
    def test_seccomp_profile_is_dict(self) -> None:
        """Test seccompProfile is a dictionary."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert isinstance(context["seccompProfile"], dict)


class TestPodSecurityContextYAMLCompatibility:
    """Unit tests for YAML serialization compatibility."""

    @pytest.mark.requirement("FR-040")
    def test_context_yaml_serializable(self) -> None:
        """Test pod security context can be serialized to YAML."""
        import yaml

        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        yaml_str = yaml.dump(context, default_flow_style=False)
        assert "runAsNonRoot: true" in yaml_str
        assert "runAsUser: 1000" in yaml_str

    @pytest.mark.requirement("FR-040")
    def test_context_yaml_roundtrip(self) -> None:
        """Test pod security context survives YAML roundtrip."""
        import yaml

        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(run_as_user=65534, fs_group=2000)
        context = config.to_pod_security_context()

        yaml_str = yaml.dump(context)
        restored: dict[str, Any] = yaml.safe_load(yaml_str)

        assert restored["runAsNonRoot"] == context["runAsNonRoot"]
        assert restored["runAsUser"] == context["runAsUser"]
        assert restored["fsGroup"] == context["fsGroup"]
        assert restored["seccompProfile"]["type"] == context["seccompProfile"]["type"]
