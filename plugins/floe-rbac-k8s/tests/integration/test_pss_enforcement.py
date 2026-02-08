"""Integration tests for Pod Security Standards enforcement.

This module validates that generated pod security contexts comply with
K8s Pod Security Standards at the 'restricted' level. Tests verify that
non-compliant configurations are rejected and compliant ones pass.

Task: T051
User Story: US5 - Pod Security Standards
Requirements: FR-040, FR-041, FR-042, FR-043, FR-044

Note:
    These tests validate the generated security context structure against
    Pod Security Standards requirements. Actual K8s admission controller
    enforcement is tested in E2E tests with a real cluster.

See Also:
    - https://kubernetes.io/docs/concepts/security/pod-security-standards/
    - ADR-0022 for restricted PSS level requirements
"""

from __future__ import annotations

from typing import Any

import pytest
from floe_core.schemas.rbac import PodSecurityConfig


class TestPodSecurityStandardsCompliance:
    """Integration tests for PSS restricted level compliance."""

    @pytest.fixture
    def default_config(self) -> PodSecurityConfig:
        """Create default PodSecurityConfig with restricted-compliant settings."""
        return PodSecurityConfig()

    @pytest.fixture
    def non_compliant_config(self) -> PodSecurityConfig:
        """Create PodSecurityConfig that violates restricted PSS."""
        return PodSecurityConfig(
            run_as_non_root=False,  # Violates restricted
            allow_privilege_escalation=True,  # Violates restricted
        )

    @pytest.mark.requirement("FR-040")
    def test_default_config_runs_as_non_root(
        self, default_config: PodSecurityConfig
    ) -> None:
        """Test default config has runAsNonRoot: true (FR-040)."""
        pod_context = default_config.to_pod_security_context()

        assert pod_context["runAsNonRoot"] is True

    @pytest.mark.requirement("FR-040")
    def test_pod_context_has_run_as_user(
        self, default_config: PodSecurityConfig
    ) -> None:
        """Test pod context includes runAsUser."""
        pod_context = default_config.to_pod_security_context()

        assert "runAsUser" in pod_context
        assert pod_context["runAsUser"] >= 1  # Non-root UID

    @pytest.mark.requirement("FR-041")
    def test_container_context_disallows_privilege_escalation(
        self, default_config: PodSecurityConfig
    ) -> None:
        """Test container context has allowPrivilegeEscalation: false (FR-041)."""
        container_context = default_config.to_container_security_context()

        assert container_context["allowPrivilegeEscalation"] is False

    @pytest.mark.requirement("FR-041")
    def test_container_context_drops_all_capabilities(
        self, default_config: PodSecurityConfig
    ) -> None:
        """Test container context drops all capabilities (FR-041)."""
        container_context = default_config.to_container_security_context()

        assert "capabilities" in container_context
        assert "drop" in container_context["capabilities"]
        assert "ALL" in container_context["capabilities"]["drop"]

    @pytest.mark.requirement("FR-042")
    def test_pod_context_has_seccomp_runtime_default(
        self, default_config: PodSecurityConfig
    ) -> None:
        """Test pod context has seccompProfile: RuntimeDefault (FR-042)."""
        pod_context = default_config.to_pod_security_context()

        assert "seccompProfile" in pod_context
        assert pod_context["seccompProfile"]["type"] == "RuntimeDefault"

    @pytest.mark.requirement("FR-043")
    def test_container_context_has_read_only_root_filesystem(
        self, default_config: PodSecurityConfig
    ) -> None:
        """Test container context has readOnlyRootFilesystem: true (FR-043)."""
        container_context = default_config.to_container_security_context()

        assert container_context["readOnlyRootFilesystem"] is True

    @pytest.mark.requirement("FR-044")
    def test_pod_context_has_configurable_uid_gid(self) -> None:
        """Test UID/GID can be configured (FR-044)."""
        config = PodSecurityConfig(
            run_as_user=2000,
            run_as_group=2000,
            fs_group=2000,
        )
        pod_context = config.to_pod_security_context()

        assert pod_context["runAsUser"] == 2000
        assert pod_context["runAsGroup"] == 2000
        assert pod_context["fsGroup"] == 2000

    @pytest.mark.requirement("FR-044")
    def test_default_uid_gid_is_1000(self, default_config: PodSecurityConfig) -> None:
        """Test default UID/GID is 1000 (FR-044)."""
        pod_context = default_config.to_pod_security_context()

        assert pod_context["runAsUser"] == 1000
        assert pod_context["runAsGroup"] == 1000
        assert pod_context["fsGroup"] == 1000


class TestPodSecurityNonCompliantOutput:
    """Tests validating output values when non-compliant settings are requested.

    Note:
        These tests verify that PodSecurityConfig correctly produces the requested
        (non-compliant) values in its output. They do NOT test actual K8s PSS
        admission rejection - that requires E2E tests with a real cluster.

        The tests ensure the config model correctly reflects user settings, even
        when those settings would violate PSS restricted level.
    """

    @pytest.mark.requirement("FR-040")
    def test_config_produces_run_as_non_root_false_when_disabled(self) -> None:
        """Test config produces runAsNonRoot: false when run_as_non_root=False.

        Note: This output would fail PSS restricted admission in a real cluster.
        """
        config = PodSecurityConfig(run_as_non_root=False)
        pod_context = config.to_pod_security_context()

        assert pod_context["runAsNonRoot"] is False

    @pytest.mark.requirement("FR-041")
    def test_config_produces_privilege_escalation_true_when_enabled(self) -> None:
        """Test config produces allowPrivilegeEscalation: true when enabled.

        Note: This output would fail PSS restricted admission in a real cluster.
        """
        config = PodSecurityConfig(allow_privilege_escalation=True)
        container_context = config.to_container_security_context()

        assert container_context["allowPrivilegeEscalation"] is True

    @pytest.mark.requirement("FR-042")
    def test_config_produces_unconfined_seccomp_when_specified(self) -> None:
        """Test config produces Unconfined seccomp profile when specified.

        Note: This output would fail PSS restricted admission in a real cluster.
        """
        config = PodSecurityConfig(seccomp_profile_type="Unconfined")
        pod_context = config.to_pod_security_context()

        assert pod_context["seccompProfile"]["type"] == "Unconfined"


class TestPodSecurityStandardsValidation:
    """Tests for PSS compliance validation utilities."""

    def _is_pss_restricted_compliant(
        self,
        pod_context: dict[str, Any],
        container_context: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """Check if security contexts are PSS restricted compliant.

        Args:
            pod_context: Pod-level security context.
            container_context: Container-level security context.

        Returns:
            Tuple of (is_compliant, list of violations).
        """
        violations: list[str] = []

        # FR-040: runAsNonRoot must be true
        if not pod_context.get("runAsNonRoot", False):
            violations.append("Pod must have runAsNonRoot: true")

        # FR-041: allowPrivilegeEscalation must be false
        if container_context.get("allowPrivilegeEscalation", True):
            violations.append("Container must have allowPrivilegeEscalation: false")

        # FR-041: capabilities.drop must include ALL
        caps = container_context.get("capabilities", {})
        if "ALL" not in caps.get("drop", []):
            violations.append("Container must drop ALL capabilities")

        # FR-042: seccompProfile must be RuntimeDefault or Localhost
        seccomp = pod_context.get("seccompProfile", {})
        seccomp_type = seccomp.get("type", "Unconfined")
        if seccomp_type not in ("RuntimeDefault", "Localhost"):
            violations.append(
                f"Pod must have seccompProfile RuntimeDefault or Localhost, got {seccomp_type}"
            )

        return len(violations) == 0, violations

    @pytest.mark.requirement("FR-040")
    @pytest.mark.requirement("FR-041")
    @pytest.mark.requirement("FR-042")
    def test_default_config_passes_pss_validation(self) -> None:
        """Test default PodSecurityConfig passes PSS validation."""
        config = PodSecurityConfig()
        pod_context = config.to_pod_security_context()
        container_context = config.to_container_security_context()

        is_compliant, violations = self._is_pss_restricted_compliant(
            pod_context, container_context
        )

        assert is_compliant is True, f"Violations: {violations}"
        assert violations == []

    @pytest.mark.requirement("FR-040")
    @pytest.mark.requirement("FR-041")
    @pytest.mark.requirement("FR-042")
    def test_non_compliant_config_fails_pss_validation(self) -> None:
        """Test non-compliant config fails PSS validation."""
        config = PodSecurityConfig(
            run_as_non_root=False,
            allow_privilege_escalation=True,
            seccomp_profile_type="Unconfined",
        )
        pod_context = config.to_pod_security_context()
        container_context = config.to_container_security_context()

        is_compliant, violations = self._is_pss_restricted_compliant(
            pod_context, container_context
        )

        assert is_compliant is False
        assert len(violations) == 3  # runAsNonRoot, allowPrivilegeEscalation, seccomp


class TestPodSecurityContextIntegration:
    """Integration tests for security context with K8sRBACPlugin."""

    @pytest.fixture
    def plugin(self) -> Any:
        """Return a K8sRBACPlugin instance."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin()

    @pytest.mark.requirement("FR-040")
    @pytest.mark.requirement("FR-041")
    @pytest.mark.requirement("FR-042")
    @pytest.mark.requirement("FR-043")
    @pytest.mark.requirement("FR-044")
    def test_plugin_generates_compliant_security_context(self, plugin: Any) -> None:
        """Test K8sRBACPlugin generates PSS compliant security context."""
        config = PodSecurityConfig()

        result = plugin.generate_pod_security_context(config)
        pod_context = result["pod"]
        container_context = result["container"]

        # Verify FR-040: runAsNonRoot
        assert pod_context["runAsNonRoot"] is True

        # Verify FR-041: allowPrivilegeEscalation and capabilities
        assert container_context["allowPrivilegeEscalation"] is False
        assert "ALL" in container_context["capabilities"]["drop"]

        # Verify FR-042: seccompProfile
        assert pod_context["seccompProfile"]["type"] == "RuntimeDefault"

        # Verify FR-043: readOnlyRootFilesystem
        assert container_context["readOnlyRootFilesystem"] is True

        # Verify FR-044: configurable UID/GID defaults
        assert pod_context["runAsUser"] == 1000
        assert pod_context["runAsGroup"] == 1000

    @pytest.mark.requirement("FR-043")
    def test_plugin_generates_volumes_for_writable_dirs(self, plugin: Any) -> None:
        """Test K8sRBACPlugin generates volumes for writable directories (FR-043)."""
        config = PodSecurityConfig()

        result = plugin.generate_pod_security_context(config)

        # Verify volumes and volumeMounts are included
        assert "volumes" in result
        assert "volumeMounts" in result

        # Default should include /tmp
        volumes = result["volumes"]
        volume_mounts = result["volumeMounts"]

        assert len(volumes) > 0
        assert len(volume_mounts) > 0

        # Check /tmp is included
        mount_paths = {m["mountPath"] for m in volume_mounts}
        assert "/tmp" in mount_paths

        # Check volume structure
        assert "emptyDir" in volumes[0]

    @pytest.mark.requirement("FR-044")
    def test_plugin_accepts_custom_uid_gid(self, plugin: Any) -> None:
        """Test K8sRBACPlugin accepts custom UID/GID."""
        config = PodSecurityConfig(
            run_as_user=65534,  # nobody
            run_as_group=65534,
            fs_group=65534,
        )

        result = plugin.generate_pod_security_context(config)
        pod_context = result["pod"]

        assert pod_context["runAsUser"] == 65534
        assert pod_context["runAsGroup"] == 65534
        assert pod_context["fsGroup"] == 65534
