"""Unit tests for PodSecurityConfig.to_container_security_context() method.

Tests the container-level securityContext generation including
allowPrivilegeEscalation, readOnlyRootFilesystem, and capabilities.

Task: T029
User Story: US2 - Namespace Isolation
Requirements: FR-041, FR-043
"""

from __future__ import annotations

from typing import Any

import pytest


class TestContainerSecurityContextBasicStructure:
    """Unit tests for container security context structure."""

    @pytest.mark.requirement("FR-041")
    def test_context_has_allow_privilege_escalation(self) -> None:
        """Test container security context includes allowPrivilegeEscalation."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert "allowPrivilegeEscalation" in context

    @pytest.mark.requirement("FR-041")
    def test_allow_privilege_escalation_default_false(self) -> None:
        """Test allowPrivilegeEscalation defaults to False."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert context["allowPrivilegeEscalation"] is False

    @pytest.mark.requirement("FR-043")
    def test_context_has_read_only_root_filesystem(self) -> None:
        """Test container security context includes readOnlyRootFilesystem."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert "readOnlyRootFilesystem" in context

    @pytest.mark.requirement("FR-043")
    def test_read_only_root_filesystem_default_true(self) -> None:
        """Test readOnlyRootFilesystem defaults to True."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert context["readOnlyRootFilesystem"] is True

    @pytest.mark.requirement("FR-041")
    def test_context_has_capabilities(self) -> None:
        """Test container security context includes capabilities."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert "capabilities" in context


class TestContainerSecurityContextCapabilities:
    """Unit tests for capabilities in container security context."""

    @pytest.mark.requirement("FR-041")
    def test_capabilities_has_drop(self) -> None:
        """Test capabilities includes drop list."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert "drop" in context["capabilities"]

    @pytest.mark.requirement("FR-041")
    def test_capabilities_drop_all(self) -> None:
        """Test capabilities drops ALL."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert context["capabilities"]["drop"] == ["ALL"]

    @pytest.mark.requirement("FR-041")
    def test_capabilities_drop_is_list(self) -> None:
        """Test capabilities drop is a list."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert isinstance(context["capabilities"]["drop"], list)


class TestContainerSecurityContextCustomValues:
    """Unit tests for custom values in container security context."""

    @pytest.mark.requirement("FR-041")
    def test_allow_privilege_escalation_configurable(self) -> None:
        """Test allowPrivilegeEscalation is configurable."""
        from floe_core.schemas.rbac import PodSecurityConfig

        # Default is False (secure)
        config_false = PodSecurityConfig(allow_privilege_escalation=False)
        context = config_false.to_container_security_context()
        assert context["allowPrivilegeEscalation"] is False

        # Can be set to True (not recommended but allowed)
        config_true = PodSecurityConfig(allow_privilege_escalation=True)
        context = config_true.to_container_security_context()
        assert context["allowPrivilegeEscalation"] is True

    @pytest.mark.requirement("FR-043")
    def test_read_only_root_filesystem_configurable(self) -> None:
        """Test readOnlyRootFilesystem is configurable."""
        from floe_core.schemas.rbac import PodSecurityConfig

        # Default is True (secure)
        config_true = PodSecurityConfig(read_only_root_filesystem=True)
        context = config_true.to_container_security_context()
        assert context["readOnlyRootFilesystem"] is True

        # Can be set to False (not recommended but may be needed)
        config_false = PodSecurityConfig(read_only_root_filesystem=False)
        context = config_false.to_container_security_context()
        assert context["readOnlyRootFilesystem"] is False


class TestContainerSecurityContextFieldTypes:
    """Unit tests for container security context field types."""

    @pytest.mark.requirement("FR-041")
    def test_allow_privilege_escalation_is_bool(self) -> None:
        """Test allowPrivilegeEscalation is a boolean."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert isinstance(context["allowPrivilegeEscalation"], bool)

    @pytest.mark.requirement("FR-043")
    def test_read_only_root_filesystem_is_bool(self) -> None:
        """Test readOnlyRootFilesystem is a boolean."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert isinstance(context["readOnlyRootFilesystem"], bool)

    @pytest.mark.requirement("FR-041")
    def test_capabilities_is_dict(self) -> None:
        """Test capabilities is a dictionary."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert isinstance(context["capabilities"], dict)


class TestContainerSecurityContextPSSCompliance:
    """Unit tests for PSS compliance in container security context."""

    @pytest.mark.requirement("FR-041")
    def test_default_context_pss_restricted_compliant(self) -> None:
        """Test default container context is PSS restricted compliant."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        # Required for restricted PSS
        assert context["allowPrivilegeEscalation"] is False
        assert context["capabilities"]["drop"] == ["ALL"]

    @pytest.mark.requirement("FR-043")
    def test_read_only_root_for_restricted_pss(self) -> None:
        """Test readOnlyRootFilesystem for restricted PSS compliance."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        # Recommended for restricted PSS
        assert context["readOnlyRootFilesystem"] is True


class TestContainerSecurityContextYAMLCompatibility:
    """Unit tests for YAML serialization compatibility."""

    @pytest.mark.requirement("FR-041")
    def test_context_yaml_serializable(self) -> None:
        """Test container security context can be serialized to YAML."""
        import yaml

        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        yaml_str = yaml.dump(context, default_flow_style=False)
        assert "allowPrivilegeEscalation: false" in yaml_str
        assert "readOnlyRootFilesystem: true" in yaml_str

    @pytest.mark.requirement("FR-041")
    def test_context_yaml_roundtrip(self) -> None:
        """Test container security context survives YAML roundtrip."""
        import yaml

        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        context = config.to_container_security_context()

        yaml_str = yaml.dump(context)
        restored: dict[str, Any] = yaml.safe_load(yaml_str)

        assert restored["allowPrivilegeEscalation"] == context["allowPrivilegeEscalation"]
        assert restored["readOnlyRootFilesystem"] == context["readOnlyRootFilesystem"]
        assert restored["capabilities"]["drop"] == context["capabilities"]["drop"]


class TestContainerSecurityContextIntegration:
    """Integration tests for container security context with pod context."""

    @pytest.mark.requirement("FR-040")
    def test_pod_and_container_context_together(self) -> None:
        """Test pod and container contexts work together."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        pod_context = config.to_pod_security_context()
        container_context = config.to_container_security_context()

        # Both should be valid dicts
        assert isinstance(pod_context, dict)
        assert isinstance(container_context, dict)

        # Pod context has pod-level fields
        assert "runAsNonRoot" in pod_context
        assert "runAsUser" in pod_context
        assert "seccompProfile" in pod_context

        # Container context has container-level fields
        assert "allowPrivilegeEscalation" in container_context
        assert "readOnlyRootFilesystem" in container_context
        assert "capabilities" in container_context

    @pytest.mark.requirement("FR-040")
    def test_contexts_no_overlap(self) -> None:
        """Test pod and container contexts don't duplicate fields."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        pod_context = config.to_pod_security_context()
        container_context = config.to_container_security_context()

        # Container-specific fields not in pod context
        assert "allowPrivilegeEscalation" not in pod_context
        assert "readOnlyRootFilesystem" not in pod_context
        assert "capabilities" not in pod_context

        # Pod-specific fields not in container context
        assert "runAsNonRoot" not in container_context
        assert "runAsUser" not in container_context
        assert "fsGroup" not in container_context
