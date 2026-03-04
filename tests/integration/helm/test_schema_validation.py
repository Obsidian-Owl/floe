"""Conditional schema validation tests for floe-platform Helm chart.

Tests that validate conditional JSON Schema constraints in values.schema.json
are correctly enforced by Helm during template rendering. These constraints
ensure that operators cannot deploy invalid configurations silently.

Requirements tested:
    AC-28.1: Bootstrap credentials required when enabled
    AC-28.2: S3 endpoint required when S3 enabled
    AC-28.4: Custom overlays not blocked (additionalProperties: true)
    AC-28.5: Environment enum enforced (dev, qa, staging, prod, test only)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Error patterns that Helm emits on schema validation failures.
# These are checked in stderr to confirm the failure is a SCHEMA rejection,
# not a template rendering error or other unrelated failure.
SCHEMA_ERROR_INDICATOR = "values don't meet the specifications of the schema"
SCHEMA_VALIDATION_FAILED = "validation failed"

# Specific property names we expect in schema error messages to confirm
# the RIGHT field triggered the failure, not some unrelated field.
BOOTSTRAP_CLIENT_SECRET_FIELD = "clientSecret"
S3_ENDPOINT_FIELD = "endpoint"
ENVIRONMENT_FIELD = "environment"

# The exact set of valid environment values per the schema enum.
# Tests MUST verify ALL of these are accepted; a partial enum is a bug.
VALID_ENVIRONMENTS = ("dev", "qa", "staging", "prod", "test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (directory with charts/).

    Returns:
        Path to the project root.

    Raises:
        pytest.fail: If charts/ directory cannot be found.
    """
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "charts").is_dir():
            return parent
    pytest.fail("Could not find project root containing charts/ directory.")
    raise AssertionError("Unreachable")


def _helm_template(
    chart_path: Path,
    set_values: list[str],
) -> subprocess.CompletedProcess[bytes]:
    """Run helm template with the given --set overrides.

    Args:
        chart_path: Absolute path to the Helm chart.
        set_values: List of key=value strings for --set flags.

    Returns:
        CompletedProcess with stdout, stderr, and returncode.
    """
    cmd: list[str] = [
        "helm",
        "template",
        "test-schema",
        str(chart_path),
    ]
    for sv in set_values:
        cmd.extend(["--set", sv])

    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=60,
        check=False,
    )


def _stderr_text(result: subprocess.CompletedProcess[bytes]) -> str:
    """Decode stderr from a CompletedProcess, defaulting to empty string.

    Args:
        result: The completed subprocess.

    Returns:
        Decoded stderr string.
    """
    return result.stderr.decode() if result.stderr else ""


def _stdout_text(result: subprocess.CompletedProcess[bytes]) -> str:
    """Decode stdout from a CompletedProcess, defaulting to empty string.

    Args:
        result: The completed subprocess.

    Returns:
        Decoded stdout string.
    """
    return result.stdout.decode() if result.stdout else ""


# ---------------------------------------------------------------------------
# AC-28.1: Bootstrap credentials required when enabled
# ---------------------------------------------------------------------------


class TestBootstrapCredentialsRequired:
    """Tests that polaris.bootstrap.enabled=true requires a non-empty clientSecret.

    AC-28.1: When polaris.bootstrap.enabled=true, Helm install MUST fail if
    polaris.auth.bootstrapCredentials.clientSecret is empty or missing.
    This prevents deploying Polaris with no admin secret, which would leave
    the catalog unprotectable.
    """

    @pytest.mark.requirement("AC-28.1")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_bootstrap_enabled_empty_client_secret_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail when bootstrap is enabled with empty clientSecret.

        This is the primary negative-path test for AC-28.1. The schema must
        enforce that enabling bootstrap without providing a clientSecret is an
        error, not a silent deployment of an unprotected catalog.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.bootstrap.enabled=true",
                "polaris.auth.bootstrapCredentials.clientSecret=",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED when bootstrap is enabled with "
            "empty clientSecret, but it succeeded. This means the schema does "
            "not enforce AC-28.1 (bootstrap credentials required when enabled).\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        # Verify the failure is specifically a schema validation error, not some
        # unrelated template rendering issue.
        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            "helm template failed, but stderr does not indicate a schema "
            "validation error. The failure may be an unrelated template issue.\n"
            f"Expected one of: '{SCHEMA_ERROR_INDICATOR}', '{SCHEMA_VALIDATION_FAILED}'\n"
            f"STDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.1")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_bootstrap_enabled_missing_client_secret_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail when bootstrap is enabled and clientSecret is absent.

        This tests the case where clientSecret is not provided at all (relying
        on the default empty string in values.yaml). The default values.yaml
        has clientSecret: "" which should trigger the schema constraint when
        bootstrap is enabled.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.bootstrap.enabled=true",
                # Do NOT set clientSecret -- rely on default empty value
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED when bootstrap is enabled "
            "without setting clientSecret (default is empty string), but "
            "it succeeded. The schema must reject the default empty value.\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            f"helm template failed, but not due to schema validation.\nSTDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.1")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_bootstrap_enabled_with_valid_client_secret_succeeds(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed when bootstrap is enabled with a valid clientSecret.

        This is the positive control test for AC-28.1. When the operator
        provides a non-empty clientSecret, the schema constraint should
        be satisfied and template rendering should succeed.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.bootstrap.enabled=true",
                "polaris.auth.bootstrapCredentials.clientSecret=my-secret-value",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED when bootstrap is enabled with a valid "
            "clientSecret. The schema should allow this configuration.\n"
            f"STDERR: {stderr[:1000]}"
        )

        # Verify actual output was produced (not an empty render)
        stdout = _stdout_text(result)
        assert len(stdout) > 0, (
            "helm template succeeded but produced no output. "
            "Expected rendered Kubernetes manifests."
        )

    @pytest.mark.requirement("AC-28.1")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_bootstrap_disabled_empty_client_secret_allowed(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed when bootstrap is disabled even with empty clientSecret.

        The constraint only applies when polaris.bootstrap.enabled=true.
        When bootstrap is disabled (the default), the clientSecret value
        is irrelevant and should not trigger a schema error.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.bootstrap.enabled=false",
                "polaris.auth.bootstrapCredentials.clientSecret=",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED when bootstrap is disabled with empty "
            "clientSecret. The constraint should only apply when bootstrap "
            "is enabled.\n"
            f"STDERR: {stderr[:1000]}"
        )


# ---------------------------------------------------------------------------
# AC-28.2: S3 endpoint required when S3 enabled (unless MinIO provides it)
# ---------------------------------------------------------------------------


class TestS3EndpointRequired:
    """Tests that S3 enabled requires either MinIO or an explicit endpoint.

    AC-28.2: When polaris.storage.s3.enabled=true, Helm install MUST fail
    unless either minio.enabled=true OR polaris.storage.s3.endpoint is
    non-empty. This prevents deploying Polaris with S3 storage configured
    but no reachable S3 endpoint.
    """

    @pytest.mark.requirement("AC-28.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_s3_enabled_no_minio_no_endpoint_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail when S3 enabled, MinIO disabled, endpoint empty.

        This is the primary negative-path test for AC-28.2. The combination of
        S3 enabled without any way to reach an S3 endpoint is a misconfiguration
        that should be caught at schema validation time, not at runtime.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.storage.s3.enabled=true",
                "minio.enabled=false",
                "polaris.storage.s3.endpoint=",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED when S3 is enabled, MinIO is "
            "disabled, and no S3 endpoint is set. This means the schema does "
            "not enforce AC-28.2 (S3 endpoint required when S3 enabled).\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            "helm template failed, but stderr does not indicate a schema "
            "validation error. The failure may be an unrelated template issue.\n"
            f"STDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_s3_enabled_no_minio_missing_endpoint_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail when S3 enabled, MinIO disabled, endpoint not set.

        Similar to the empty-endpoint test but relies on the default value
        from values.yaml (which is an empty string). This catches the case
        where an operator enables S3 but forgets to set the endpoint.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.storage.s3.enabled=true",
                "minio.enabled=false",
                # Do NOT set endpoint -- rely on default empty value
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED when S3 is enabled with MinIO "
            "disabled and endpoint left at default (empty). The schema must "
            "reject this configuration.\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            f"helm template failed, but not due to schema validation.\nSTDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_s3_enabled_with_minio_enabled_succeeds(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed when S3 enabled and MinIO is also enabled.

        When MinIO is enabled, it provides the S3 endpoint automatically,
        so the operator does not need to set polaris.storage.s3.endpoint
        explicitly. The schema should allow this configuration.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.storage.s3.enabled=true",
                "minio.enabled=true",
                "polaris.storage.s3.endpoint=",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED when S3 and MinIO are both enabled. "
            "The schema should allow S3 without an explicit endpoint when "
            "MinIO provides the endpoint automatically.\n"
            f"STDERR: {stderr[:1000]}"
        )

        stdout = _stdout_text(result)
        assert len(stdout) > 0, "helm template succeeded but produced no output."

    @pytest.mark.requirement("AC-28.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_s3_enabled_with_explicit_endpoint_succeeds(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed when S3 enabled with an explicit endpoint.

        When the operator provides a non-empty S3 endpoint, the schema
        constraint is satisfied regardless of whether MinIO is enabled.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.storage.s3.enabled=true",
                "minio.enabled=false",
                "polaris.storage.s3.endpoint=https://s3.us-east-1.amazonaws.com",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED when S3 is enabled with an explicit "
            "endpoint. The schema should allow this configuration.\n"
            f"STDERR: {stderr[:1000]}"
        )

        stdout = _stdout_text(result)
        assert len(stdout) > 0, "helm template succeeded but produced no output."

    @pytest.mark.requirement("AC-28.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_s3_disabled_no_endpoint_allowed(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed when S3 is disabled even without endpoint.

        The S3 endpoint constraint only applies when polaris.storage.s3.enabled
        is true. When S3 is disabled, endpoint configuration is irrelevant.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.storage.s3.enabled=false",
                "minio.enabled=false",
                "polaris.storage.s3.endpoint=",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED when S3 is disabled. The endpoint "
            "constraint should only apply when S3 is enabled.\n"
            f"STDERR: {stderr[:1000]}"
        )


# ---------------------------------------------------------------------------
# AC-28.4: Custom overlays not blocked (additionalProperties: true)
# ---------------------------------------------------------------------------


class TestCustomOverlaysAllowed:
    """Tests that additionalProperties: true allows custom values.

    AC-28.4: The schema must not block custom keys that operators may need
    for site-specific configuration, subchart passthrough, or Helm
    lifecycle hooks. All objects in the schema should set
    additionalProperties: true (or omit it, which defaults to true).
    """

    @pytest.mark.requirement("AC-28.4")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_top_level_custom_key_allowed(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed with a custom top-level key.

        Operators may add custom top-level keys for their own use or for
        subcharts that the schema does not explicitly define. The schema
        must not reject these.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "customKey.foo=bar",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with a custom top-level key (customKey.foo=bar). "
            "The schema must allow additional properties to support custom overlays.\n"
            f"STDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.4")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_nested_custom_key_in_polaris_allowed(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed with a custom key nested under polaris.

        Operators may need to pass additional configuration to Polaris
        that the schema does not explicitly enumerate. The polaris object
        must allow additional properties.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.customAnnotation=my-value",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with a custom key under polaris "
            "(polaris.customAnnotation=my-value). The polaris object must "
            "allow additional properties.\n"
            f"STDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.4")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_nested_custom_key_in_global_allowed(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed with a custom key nested under global.

        The global object is commonly extended by subcharts. It must
        allow additional properties beyond those defined in the schema.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "global.myCustomSetting=enabled",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with a custom key under global "
            "(global.myCustomSetting=enabled). The global object must "
            "allow additional properties for subchart compatibility.\n"
            f"STDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.4")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_multiple_custom_keys_at_different_levels_allowed(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed with multiple custom keys at various depths.

        This exercises the additionalProperties setting across multiple
        schema objects simultaneously, catching cases where only some
        objects allow extra properties.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "siteConfig.region=eu-west-1",
                "global.customFlag=true",
                "polaris.extraLabels.team=platform",
                "dagster.customEnvVar=CUSTOM_VALUE",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with custom keys at multiple levels. "
            "All schema objects must allow additional properties.\n"
            f"STDERR: {stderr[:1000]}"
        )


# ---------------------------------------------------------------------------
# AC-28.5: Environment enum enforced
# ---------------------------------------------------------------------------


class TestEnvironmentEnumEnforced:
    """Tests that global.environment only accepts the defined enum values.

    AC-28.5: global.environment MUST only accept ["dev", "qa", "staging",
    "prod", "test"]. Any other value (typos like "production", random strings
    like "invalid", numeric strings, empty strings) MUST be rejected at
    install time via schema validation. This prevents silent misconfiguration
    where an operator deploys to a non-existent environment tier.
    """

    # -- Positive controls: each valid enum value MUST be accepted ----------

    @pytest.mark.requirement("AC-28.5")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_valid_environment_dev_accepted(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed with global.environment=dev.

        'dev' is the default development environment and the schema default
        value. This is the baseline positive control confirming the enum
        includes 'dev'.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=["global.environment=dev"],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with global.environment=dev. "
            "'dev' is a valid enum value and MUST be accepted.\n"
            f"STDERR: {stderr[:1000]}"
        )

        stdout = _stdout_text(result)
        assert len(stdout) > 0, (
            "helm template succeeded but produced no output. "
            "Expected rendered Kubernetes manifests."
        )

    @pytest.mark.requirement("AC-28.5")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_valid_environment_prod_accepted(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed with global.environment=prod.

        'prod' is the production environment value. This positive control
        confirms operators can deploy to production with the correct
        enum spelling (not 'production').
        """
        result = _helm_template(
            platform_chart_path,
            set_values=["global.environment=prod"],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with global.environment=prod. "
            "'prod' is a valid enum value and MUST be accepted.\n"
            f"STDERR: {stderr[:1000]}"
        )

        stdout = _stdout_text(result)
        assert len(stdout) > 0, (
            "helm template succeeded but produced no output. "
            "Expected rendered Kubernetes manifests."
        )

    @pytest.mark.requirement("AC-28.5")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_valid_environment_test_accepted(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed with global.environment=test.

        'test' is the CI/test environment value. This positive control
        ensures the enum includes the value used in automated testing
        pipelines.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=["global.environment=test"],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with global.environment=test. "
            "'test' is a valid enum value and MUST be accepted.\n"
            f"STDERR: {stderr[:1000]}"
        )

        stdout = _stdout_text(result)
        assert len(stdout) > 0, (
            "helm template succeeded but produced no output. "
            "Expected rendered Kubernetes manifests."
        )

    @pytest.mark.requirement("AC-28.5")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_valid_environment_qa_accepted(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed with global.environment=qa.

        'qa' is the quality assurance environment. Without this test,
        a partial enum missing 'qa' would go undetected.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=["global.environment=qa"],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with global.environment=qa. "
            "'qa' is a valid enum value and MUST be accepted.\n"
            f"STDERR: {stderr[:1000]}"
        )

        stdout = _stdout_text(result)
        assert len(stdout) > 0, (
            "helm template succeeded but produced no output. "
            "Expected rendered Kubernetes manifests."
        )

    @pytest.mark.requirement("AC-28.5")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_valid_environment_staging_accepted(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed with global.environment=staging.

        'staging' is the pre-production environment. Without this test,
        a partial enum missing 'staging' would go undetected.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=["global.environment=staging"],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with global.environment=staging. "
            "'staging' is a valid enum value and MUST be accepted.\n"
            f"STDERR: {stderr[:1000]}"
        )

        stdout = _stdout_text(result)
        assert len(stdout) > 0, (
            "helm template succeeded but produced no output. "
            "Expected rendered Kubernetes manifests."
        )

    # -- Negative controls: invalid values MUST be rejected -----------------

    @pytest.mark.requirement("AC-28.5")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_invalid_environment_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail with global.environment=invalid.

        An arbitrary string that is not in the enum MUST be rejected at
        install time. This is the primary negative test confirming the
        enum constraint is enforced, not just advisory.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=["global.environment=invalid"],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED with global.environment=invalid, "
            "but it succeeded. This means the schema does not enforce AC-28.5 "
            "(environment enum constraint). The enum MUST reject values outside "
            "['dev', 'qa', 'staging', 'prod', 'test'].\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        # Verify the failure is specifically a schema validation error,
        # not an unrelated template rendering issue.
        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            "helm template failed, but stderr does not indicate a schema "
            "validation error. The failure may be an unrelated template issue.\n"
            f"Expected one of: '{SCHEMA_ERROR_INDICATOR}', '{SCHEMA_VALIDATION_FAILED}'\n"
            f"STDERR: {stderr[:1000]}"
        )

        # Verify the error references the environment field specifically,
        # not some other unrelated schema constraint.
        assert ENVIRONMENT_FIELD in stderr_lower or "enum" in stderr_lower, (
            "Schema validation failed, but the error does not reference "
            f"'{ENVIRONMENT_FIELD}' or 'enum'. The failure may be caused by a "
            "different schema constraint, not the environment enum.\n"
            f"STDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.5")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_typo_environment_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail with global.environment=production (common typo).

        'production' is the most common typo for 'prod'. The schema must
        reject it rather than silently deploying with a misconfigured
        environment label. This test specifically guards against operators
        who use the full word instead of the abbreviated enum value.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=["global.environment=production"],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED with global.environment=production "
            "(a common typo for 'prod'), but it succeeded. The enum MUST only "
            "accept ['dev', 'qa', 'staging', 'prod', 'test']. "
            "'production' is NOT a valid value.\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            "helm template failed with global.environment=production, but "
            "stderr does not indicate a schema validation error.\n"
            f"Expected one of: '{SCHEMA_ERROR_INDICATOR}', '{SCHEMA_VALIDATION_FAILED}'\n"
            f"STDERR: {stderr[:1000]}"
        )
