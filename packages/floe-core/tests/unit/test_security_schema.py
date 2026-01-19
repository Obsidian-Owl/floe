"""Unit tests for SecurityConfig schema.

Tests the SecurityConfig, RBACConfig, and PodSecurityLevelConfig models
for manifest.yaml security section configuration.

Task: T014
Requirements: FR-001 (Security Configuration), FR-010 (RBAC Settings)
Contract: specs/7b-k8s-rbac/contracts/security-config-schema.md
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.schemas.security import (
    PodSecurityLevelConfig,
    RBACConfig,
    SecurityConfig,
)


class TestRBACConfig:
    """Unit tests for RBACConfig model."""

    @pytest.mark.requirement("FR-001")
    def test_create_with_defaults(self) -> None:
        """Test RBACConfig uses correct defaults."""
        config = RBACConfig()

        assert config.enabled is True
        assert config.job_service_account == "auto"
        assert config.cluster_scope is False

    @pytest.mark.requirement("FR-001")
    def test_create_with_all_fields(self) -> None:
        """Test RBACConfig with all fields specified."""
        config = RBACConfig(
            enabled=False,
            job_service_account="manual",
            cluster_scope=True,
        )

        assert config.enabled is False
        assert config.job_service_account == "manual"
        assert config.cluster_scope is True

    @pytest.mark.requirement("FR-001")
    def test_job_service_account_auto(self) -> None:
        """Test job_service_account accepts 'auto' value."""
        config = RBACConfig(job_service_account="auto")
        assert config.job_service_account == "auto"

    @pytest.mark.requirement("FR-001")
    def test_job_service_account_manual(self) -> None:
        """Test job_service_account accepts 'manual' value."""
        config = RBACConfig(job_service_account="manual")
        assert config.job_service_account == "manual"

    @pytest.mark.requirement("FR-001")
    def test_job_service_account_invalid_value(self) -> None:
        """Test job_service_account rejects invalid values."""
        with pytest.raises(ValidationError, match="Input should be 'auto' or 'manual'"):
            RBACConfig(job_service_account="invalid")

    @pytest.mark.requirement("FR-001")
    def test_enabled_true(self) -> None:
        """Test enabled accepts True."""
        config = RBACConfig(enabled=True)
        assert config.enabled is True

    @pytest.mark.requirement("FR-001")
    def test_enabled_false(self) -> None:
        """Test enabled accepts False."""
        config = RBACConfig(enabled=False)
        assert config.enabled is False

    @pytest.mark.requirement("FR-001")
    def test_cluster_scope_true(self) -> None:
        """Test cluster_scope accepts True."""
        config = RBACConfig(cluster_scope=True)
        assert config.cluster_scope is True

    @pytest.mark.requirement("FR-001")
    def test_cluster_scope_false(self) -> None:
        """Test cluster_scope accepts False."""
        config = RBACConfig(cluster_scope=False)
        assert config.cluster_scope is False

    @pytest.mark.requirement("FR-001")
    def test_model_is_frozen(self) -> None:
        """Test RBACConfig is immutable (frozen)."""
        config = RBACConfig()

        with pytest.raises(ValidationError):
            config.enabled = False  # type: ignore[misc]

    @pytest.mark.requirement("FR-001")
    def test_extra_fields_forbidden(self) -> None:
        """Test RBACConfig rejects extra fields."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            RBACConfig(extra_field="value")  # type: ignore[call-arg]


class TestPodSecurityLevelConfig:
    """Unit tests for PodSecurityLevelConfig model."""

    @pytest.mark.requirement("FR-040")
    def test_create_with_defaults(self) -> None:
        """Test PodSecurityLevelConfig uses correct defaults."""
        config = PodSecurityLevelConfig()

        assert config.jobs_level == "restricted"
        assert config.platform_level == "baseline"

    @pytest.mark.requirement("FR-040")
    def test_create_with_all_fields(self) -> None:
        """Test PodSecurityLevelConfig with all fields specified."""
        config = PodSecurityLevelConfig(
            jobs_level="baseline",
            platform_level="restricted",
        )

        assert config.jobs_level == "baseline"
        assert config.platform_level == "restricted"

    @pytest.mark.requirement("FR-040")
    def test_jobs_level_privileged(self) -> None:
        """Test jobs_level accepts 'privileged' value."""
        config = PodSecurityLevelConfig(jobs_level="privileged")
        assert config.jobs_level == "privileged"

    @pytest.mark.requirement("FR-040")
    def test_jobs_level_baseline(self) -> None:
        """Test jobs_level accepts 'baseline' value."""
        config = PodSecurityLevelConfig(jobs_level="baseline")
        assert config.jobs_level == "baseline"

    @pytest.mark.requirement("FR-040")
    def test_jobs_level_restricted(self) -> None:
        """Test jobs_level accepts 'restricted' value."""
        config = PodSecurityLevelConfig(jobs_level="restricted")
        assert config.jobs_level == "restricted"

    @pytest.mark.requirement("FR-040")
    def test_jobs_level_invalid_value(self) -> None:
        """Test jobs_level rejects invalid values."""
        with pytest.raises(
            ValidationError,
            match="Input should be 'privileged', 'baseline' or 'restricted'",
        ):
            PodSecurityLevelConfig(jobs_level="invalid")

    @pytest.mark.requirement("FR-040")
    def test_platform_level_privileged(self) -> None:
        """Test platform_level accepts 'privileged' value."""
        config = PodSecurityLevelConfig(platform_level="privileged")
        assert config.platform_level == "privileged"

    @pytest.mark.requirement("FR-040")
    def test_platform_level_baseline(self) -> None:
        """Test platform_level accepts 'baseline' value."""
        config = PodSecurityLevelConfig(platform_level="baseline")
        assert config.platform_level == "baseline"

    @pytest.mark.requirement("FR-040")
    def test_platform_level_restricted(self) -> None:
        """Test platform_level accepts 'restricted' value."""
        config = PodSecurityLevelConfig(platform_level="restricted")
        assert config.platform_level == "restricted"

    @pytest.mark.requirement("FR-040")
    def test_platform_level_invalid_value(self) -> None:
        """Test platform_level rejects invalid values."""
        with pytest.raises(
            ValidationError,
            match="Input should be 'privileged', 'baseline' or 'restricted'",
        ):
            PodSecurityLevelConfig(platform_level="invalid")

    @pytest.mark.requirement("FR-040")
    def test_model_is_frozen(self) -> None:
        """Test PodSecurityLevelConfig is immutable (frozen)."""
        config = PodSecurityLevelConfig()

        with pytest.raises(ValidationError):
            config.jobs_level = "privileged"  # type: ignore[misc]

    @pytest.mark.requirement("FR-040")
    def test_extra_fields_forbidden(self) -> None:
        """Test PodSecurityLevelConfig rejects extra fields."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            PodSecurityLevelConfig(extra_field="value")  # type: ignore[call-arg]


class TestSecurityConfig:
    """Unit tests for SecurityConfig model."""

    @pytest.mark.requirement("FR-001")
    def test_create_with_defaults(self) -> None:
        """Test SecurityConfig uses correct defaults."""
        config = SecurityConfig()

        assert config.rbac.enabled is True
        assert config.rbac.job_service_account == "auto"
        assert config.rbac.cluster_scope is False
        assert config.pod_security.jobs_level == "restricted"
        assert config.pod_security.platform_level == "baseline"
        assert config.namespace_isolation == "strict"

    @pytest.mark.requirement("FR-001")
    def test_create_with_all_fields(self) -> None:
        """Test SecurityConfig with all fields specified."""
        config = SecurityConfig(
            rbac=RBACConfig(
                enabled=False,
                job_service_account="manual",
                cluster_scope=True,
            ),
            pod_security=PodSecurityLevelConfig(
                jobs_level="baseline",
                platform_level="privileged",
            ),
            namespace_isolation="permissive",
        )

        assert config.rbac.enabled is False
        assert config.rbac.job_service_account == "manual"
        assert config.rbac.cluster_scope is True
        assert config.pod_security.jobs_level == "baseline"
        assert config.pod_security.platform_level == "privileged"
        assert config.namespace_isolation == "permissive"

    @pytest.mark.requirement("FR-001")
    def test_namespace_isolation_strict(self) -> None:
        """Test namespace_isolation accepts 'strict' value."""
        config = SecurityConfig(namespace_isolation="strict")
        assert config.namespace_isolation == "strict"

    @pytest.mark.requirement("FR-001")
    def test_namespace_isolation_permissive(self) -> None:
        """Test namespace_isolation accepts 'permissive' value."""
        config = SecurityConfig(namespace_isolation="permissive")
        assert config.namespace_isolation == "permissive"

    @pytest.mark.requirement("FR-001")
    def test_namespace_isolation_invalid_value(self) -> None:
        """Test namespace_isolation rejects invalid values."""
        with pytest.raises(
            ValidationError,
            match="Input should be 'strict' or 'permissive'",
        ):
            SecurityConfig(namespace_isolation="invalid")

    @pytest.mark.requirement("FR-001")
    def test_nested_rbac_config(self) -> None:
        """Test SecurityConfig accepts nested RBACConfig."""
        rbac = RBACConfig(enabled=True, job_service_account="auto")
        config = SecurityConfig(rbac=rbac)

        assert config.rbac == rbac
        assert config.rbac.enabled is True

    @pytest.mark.requirement("FR-001")
    def test_nested_pod_security_config(self) -> None:
        """Test SecurityConfig accepts nested PodSecurityLevelConfig."""
        pod_security = PodSecurityLevelConfig(jobs_level="restricted")
        config = SecurityConfig(pod_security=pod_security)

        assert config.pod_security == pod_security
        assert config.pod_security.jobs_level == "restricted"

    @pytest.mark.requirement("FR-001")
    def test_model_is_frozen(self) -> None:
        """Test SecurityConfig is immutable (frozen)."""
        config = SecurityConfig()

        with pytest.raises(ValidationError):
            config.namespace_isolation = "permissive"  # type: ignore[misc]

    @pytest.mark.requirement("FR-001")
    def test_extra_fields_forbidden(self) -> None:
        """Test SecurityConfig rejects extra fields."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            SecurityConfig(extra_field="value")  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-001")
    def test_create_from_dict(self) -> None:
        """Test SecurityConfig can be created from dictionary."""
        data = {
            "rbac": {
                "enabled": True,
                "job_service_account": "auto",
                "cluster_scope": False,
            },
            "pod_security": {
                "jobs_level": "restricted",
                "platform_level": "baseline",
            },
            "namespace_isolation": "strict",
        }

        config = SecurityConfig.model_validate(data)

        assert config.rbac.enabled is True
        assert config.pod_security.jobs_level == "restricted"
        assert config.namespace_isolation == "strict"

    @pytest.mark.requirement("FR-001")
    def test_partial_dict_uses_defaults(self) -> None:
        """Test SecurityConfig uses defaults for missing fields in dict."""
        data = {
            "namespace_isolation": "permissive",
        }

        config = SecurityConfig.model_validate(data)

        # Explicit field
        assert config.namespace_isolation == "permissive"
        # Defaults applied
        assert config.rbac.enabled is True
        assert config.pod_security.jobs_level == "restricted"


class TestSecurityConfigHashability:
    """Unit tests for hashability (frozen models)."""

    @pytest.mark.requirement("FR-001")
    def test_rbac_config_can_be_hashed(self) -> None:
        """Test RBACConfig can be used as dictionary key."""
        config = RBACConfig()
        mapping: dict[object, str] = {config: "value"}
        assert mapping[config] == "value"

    @pytest.mark.requirement("FR-001")
    def test_pod_security_config_can_be_hashed(self) -> None:
        """Test PodSecurityLevelConfig can be used as dictionary key."""
        config = PodSecurityLevelConfig()
        mapping: dict[object, str] = {config: "value"}
        assert mapping[config] == "value"

    @pytest.mark.requirement("FR-001")
    def test_security_config_can_be_hashed(self) -> None:
        """Test SecurityConfig can be used as dictionary key."""
        config = SecurityConfig()
        mapping: dict[object, str] = {config: "value"}
        assert mapping[config] == "value"

    @pytest.mark.requirement("FR-001")
    def test_equal_configs_have_same_hash(self) -> None:
        """Test equal configurations have the same hash."""
        config1 = SecurityConfig()
        config2 = SecurityConfig()

        assert config1 == config2
        assert hash(config1) == hash(config2)

    @pytest.mark.requirement("FR-001")
    def test_different_configs_are_not_equal(self) -> None:
        """Test different configurations are not equal."""
        config1 = SecurityConfig(namespace_isolation="strict")
        config2 = SecurityConfig(namespace_isolation="permissive")

        assert config1 != config2


class TestSecurityConfigJsonSchema:
    """Unit tests for JSON schema generation."""

    @pytest.mark.requirement("FR-001")
    def test_rbac_config_json_schema(self) -> None:
        """Test RBACConfig generates valid JSON schema."""
        schema = RBACConfig.model_json_schema()

        assert "properties" in schema
        assert "enabled" in schema["properties"]
        assert "job_service_account" in schema["properties"]
        assert "cluster_scope" in schema["properties"]

    @pytest.mark.requirement("FR-001")
    def test_pod_security_config_json_schema(self) -> None:
        """Test PodSecurityLevelConfig generates valid JSON schema."""
        schema = PodSecurityLevelConfig.model_json_schema()

        assert "properties" in schema
        assert "jobs_level" in schema["properties"]
        assert "platform_level" in schema["properties"]

    @pytest.mark.requirement("FR-001")
    def test_security_config_json_schema(self) -> None:
        """Test SecurityConfig generates valid JSON schema."""
        schema = SecurityConfig.model_json_schema()

        assert "properties" in schema
        assert "rbac" in schema["properties"]
        assert "pod_security" in schema["properties"]
        assert "namespace_isolation" in schema["properties"]

    @pytest.mark.requirement("FR-001")
    def test_json_schema_has_enum_for_literals(self) -> None:
        """Test JSON schema includes enum values for Literal types."""
        schema = RBACConfig.model_json_schema()

        # job_service_account should have enum
        job_sa_schema = schema["properties"]["job_service_account"]
        assert "enum" in job_sa_schema
        assert "auto" in job_sa_schema["enum"]
        assert "manual" in job_sa_schema["enum"]
