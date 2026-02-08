"""Unit tests for seccompProfile generation in PodSecurityConfig.

Tests the seccompProfile field generation for pod-level security context
to ensure compliance with Pod Security Standards.

Task: T052
User Story: US5 - Pod Security Standards
Requirements: FR-042
"""

from __future__ import annotations

import pytest


class TestSeccompProfileGeneration:
    """Unit tests for seccompProfile generation."""

    @pytest.mark.requirement("FR-042")
    def test_default_seccomp_profile_is_runtime_default(self) -> None:
        """Test default seccompProfile type is RuntimeDefault (FR-042)."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()

        assert config.seccomp_profile_type == "RuntimeDefault"

    @pytest.mark.requirement("FR-042")
    def test_seccomp_profile_in_pod_context(self) -> None:
        """Test seccompProfile is included in pod security context."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        pod_context = config.to_pod_security_context()

        assert "seccompProfile" in pod_context
        assert isinstance(pod_context["seccompProfile"], dict)
        assert "type" in pod_context["seccompProfile"]

    @pytest.mark.requirement("FR-042")
    def test_seccomp_profile_type_in_context(self) -> None:
        """Test seccompProfile type value in generated context."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        pod_context = config.to_pod_security_context()

        assert pod_context["seccompProfile"]["type"] == "RuntimeDefault"


class TestSeccompProfileTypes:
    """Unit tests for different seccompProfile types."""

    @pytest.mark.requirement("FR-042")
    def test_runtime_default_type(self) -> None:
        """Test RuntimeDefault seccompProfile type."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(seccomp_profile_type="RuntimeDefault")
        pod_context = config.to_pod_security_context()

        assert pod_context["seccompProfile"]["type"] == "RuntimeDefault"

    @pytest.mark.requirement("FR-042")
    def test_localhost_type(self) -> None:
        """Test Localhost seccompProfile type."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(seccomp_profile_type="Localhost")
        pod_context = config.to_pod_security_context()

        assert pod_context["seccompProfile"]["type"] == "Localhost"

    @pytest.mark.requirement("FR-042")
    def test_unconfined_type(self) -> None:
        """Test Unconfined seccompProfile type (non-compliant with restricted PSS)."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(seccomp_profile_type="Unconfined")
        pod_context = config.to_pod_security_context()

        # Note: Unconfined is allowed by schema but violates restricted PSS
        assert pod_context["seccompProfile"]["type"] == "Unconfined"


class TestSeccompProfileValidation:
    """Unit tests for seccompProfile validation."""

    @pytest.mark.requirement("FR-042")
    def test_invalid_seccomp_type_rejected(self) -> None:
        """Test invalid seccompProfile type is rejected by validation."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import PodSecurityConfig

        with pytest.raises(ValidationError):
            PodSecurityConfig(seccomp_profile_type="InvalidType")  # type: ignore[arg-type]

    @pytest.mark.requirement("FR-042")
    def test_valid_seccomp_types_accepted(self) -> None:
        """Test all valid seccompProfile types are accepted."""
        from floe_core.schemas.rbac import PodSecurityConfig

        valid_types = ["RuntimeDefault", "Localhost", "Unconfined"]

        for seccomp_type in valid_types:
            config = PodSecurityConfig(seccomp_profile_type=seccomp_type)  # type: ignore[arg-type]
            assert config.seccomp_profile_type == seccomp_type


class TestSeccompProfileCompliance:
    """Unit tests for PSS compliance of seccompProfile."""

    @pytest.mark.requirement("FR-042")
    def test_runtime_default_is_pss_compliant(self) -> None:
        """Test RuntimeDefault is compliant with PSS restricted level."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(seccomp_profile_type="RuntimeDefault")

        # RuntimeDefault is required or allowed by restricted PSS
        assert config.seccomp_profile_type in ("RuntimeDefault", "Localhost")

    @pytest.mark.requirement("FR-042")
    def test_localhost_is_pss_compliant(self) -> None:
        """Test Localhost is compliant with PSS restricted level."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(seccomp_profile_type="Localhost")

        # Localhost is allowed by restricted PSS
        assert config.seccomp_profile_type in ("RuntimeDefault", "Localhost")

    @pytest.mark.requirement("FR-042")
    def test_unconfined_is_not_pss_compliant(self) -> None:
        """Test Unconfined is NOT compliant with PSS restricted level."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(seccomp_profile_type="Unconfined")

        # Unconfined violates restricted PSS
        pss_compliant_types = ("RuntimeDefault", "Localhost")
        assert config.seccomp_profile_type not in pss_compliant_types


class TestSeccompProfileContextStructure:
    """Unit tests for seccompProfile context structure."""

    @pytest.mark.requirement("FR-042")
    def test_pod_context_structure_matches_k8s_api(self) -> None:
        """Test pod security context structure matches K8s API."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        pod_context = config.to_pod_security_context()

        # Structure should match K8s PodSecurityContext
        expected_keys = {
            "runAsNonRoot",
            "runAsUser",
            "runAsGroup",
            "fsGroup",
            "seccompProfile",
        }
        assert expected_keys.issubset(set(pod_context.keys()))

        # seccompProfile should be a SeccompProfile object
        assert isinstance(pod_context["seccompProfile"], dict)
        assert "type" in pod_context["seccompProfile"]

    @pytest.mark.requirement("FR-042")
    def test_seccomp_profile_is_serializable(self) -> None:
        """Test seccompProfile is JSON serializable for K8s manifests."""
        import json

        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        pod_context = config.to_pod_security_context()

        # Should be serializable without error
        json_str = json.dumps(pod_context)
        assert "seccompProfile" in json_str
        assert "RuntimeDefault" in json_str

    @pytest.mark.requirement("FR-042")
    def test_seccomp_profile_type_is_camel_case(self) -> None:
        """Test seccompProfile type field uses K8s camelCase."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        pod_context = config.to_pod_security_context()

        # K8s API uses "type" not "Type" or "profile_type"
        assert "type" in pod_context["seccompProfile"]
        # Value should be PascalCase as per K8s API
        assert pod_context["seccompProfile"]["type"][0].isupper()
