"""Conditional schema validation tests for floe-platform Helm chart.

Tests that validate conditional JSON Schema constraints in values.schema.json
are correctly enforced by Helm during template rendering. These constraints
ensure that operators cannot deploy invalid configurations silently.

Note: test_values_schema.py in this directory tests the same schema via Python
jsonschema (static analysis layer). This file tests via Helm CLI (runtime layer).

Requirements tested:
    AC-28.1: Bootstrap credentials required when enabled
    AC-28.2: S3 endpoint required when S3 enabled
    AC-28.3: Both values files pass enhanced schema (no regressions)
    AC-28.4: Custom overlays not blocked (additionalProperties: true)
    AC-28.5: Environment enum enforced (dev, qa, staging, prod, test, demo only)
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
GRANTS_FIELD = "grants"
PRIVILEGES_FIELD = "privileges"

# The exact set of valid environment values per the schema enum.
# Tests MUST verify ALL of these are accepted; a partial enum is a bug.
VALID_ENVIRONMENTS = ("dev", "qa", "staging", "prod", "test", "demo")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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

        # Verify the error references the clientSecret field specifically,
        # not some other unrelated schema constraint.
        assert BOOTSTRAP_CLIENT_SECRET_FIELD in stderr_lower or "minlength" in stderr_lower, (
            "Schema validation failed, but the error does not reference "
            f"'{BOOTSTRAP_CLIENT_SECRET_FIELD}'. The failure may be caused by a "
            "different schema constraint, not the bootstrap credentials requirement.\n"
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

        # Verify the error references the clientSecret field specifically.
        assert BOOTSTRAP_CLIENT_SECRET_FIELD in stderr_lower or "minlength" in stderr_lower, (
            "Schema validation failed, but the error does not reference "
            f"'{BOOTSTRAP_CLIENT_SECRET_FIELD}'. The failure may be caused by a "
            "different schema constraint, not the bootstrap credentials requirement.\n"
            f"STDERR: {stderr[:1000]}"
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
                "polaris.auth.bootstrapCredentials.clientSecret=SCHEMA-TEST-SENTINEL",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED when bootstrap is enabled with a valid "
            "clientSecret. The schema should allow this configuration.\n"
            f"STDERR: {stderr[:1000]}"
        )

        # Verify actual K8s manifest output was produced
        stdout = _stdout_text(result)
        assert "apiVersion:" in stdout or "kind:" in stdout, (
            "helm template produced output but it does not contain K8s manifests."
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

    @pytest.mark.requirement("AC-28.1")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_bootstrap_enabled_whitespace_client_secret_accepted(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Whitespace-only clientSecret passes minLength: 1.

        The schema validates presence, not strength.

        The schema uses minLength: 1 which counts whitespace characters.
        This is intentional: the schema validates that SOME value was
        provided, not that it is cryptographically strong. Strength
        validation belongs in the application layer, not the schema.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.bootstrap.enabled=true",
                "polaris.auth.bootstrapCredentials.clientSecret= ",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with a whitespace-only clientSecret. "
            "The schema uses minLength: 1 which should accept whitespace. "
            "Strength validation is the application's responsibility.\n"
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

        # Verify the error references the S3 endpoint or MinIO constraint.
        s3_field_referenced = (
            S3_ENDPOINT_FIELD in stderr_lower or "minio" in stderr_lower or "anyof" in stderr_lower
        )
        assert s3_field_referenced, (
            "Schema validation failed, but the error does not reference "
            f"'{S3_ENDPOINT_FIELD}' or 'minio'. The failure may be caused by a "
            "different schema constraint, not the S3 endpoint requirement.\n"
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

        # Verify the error references the S3 endpoint or MinIO constraint.
        s3_field_referenced = (
            S3_ENDPOINT_FIELD in stderr_lower or "minio" in stderr_lower or "anyof" in stderr_lower
        )
        assert s3_field_referenced, (
            "Schema validation failed, but the error does not reference "
            f"'{S3_ENDPOINT_FIELD}' or 'minio'. The failure may be caused by a "
            "different schema constraint, not the S3 endpoint requirement.\n"
            f"STDERR: {stderr[:1000]}"
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
        assert "apiVersion:" in stdout or "kind:" in stdout, (
            "helm template produced output but it does not contain K8s manifests."
        )

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
        assert "apiVersion:" in stdout or "kind:" in stdout, (
            "helm template produced output but it does not contain K8s manifests."
        )

    @pytest.mark.requirement("AC-28.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_s3_enabled_with_both_minio_and_endpoint_succeeds(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed when both MinIO and explicit endpoint are set.

        The schema uses anyOf (not oneOf), so providing both an enabled MinIO
        AND an explicit S3 endpoint should be accepted. This test guards
        against accidentally using oneOf which would reject this valid case.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.storage.s3.enabled=true",
                "minio.enabled=true",
                "polaris.storage.s3.endpoint=https://s3.example.com",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED when both MinIO and S3 endpoint are set. "
            "The schema should use anyOf, not oneOf.\n"
            f"STDERR: {stderr[:1000]}"
        )

        stdout = _stdout_text(result)
        assert "apiVersion:" in stdout or "kind:" in stdout, (
            "helm template produced output but it does not contain K8s manifests."
        )

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
# AC-28.6: Polaris bootstrap grants schema validation
# ---------------------------------------------------------------------------


class TestPolarisBootstrapGrantsSchema:
    """Tests that polaris.bootstrap.grants is validated by values.schema.json.

    AC-28.6: Polaris grant settings MUST be rejected by Helm schema validation
    when booleans, role names, or privilege lists are malformed. This catches
    operator mistakes before the bootstrap Job runs.
    """

    @pytest.mark.requirement("AC-28.6")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_grants_enabled_string_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail when grants.enabled is a string."""
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.bootstrap.grants.enabled=not-a-bool",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED when polaris.bootstrap.grants.enabled "
            "is a string, but it succeeded. This means the schema does not enforce "
            "the grants.enabled boolean contract.\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            f"helm template failed, but not due to schema validation.\nSTDERR: {stderr[:1000]}"
        )
        assert GRANTS_FIELD in stderr_lower or "boolean" in stderr_lower, (
            "Schema validation failed, but the error does not reference the grants "
            f"boolean constraint.\nSTDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.6")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_grants_privileges_scalar_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail when grants.privileges is not an array."""
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.bootstrap.grants.privileges=CATALOG_MANAGE_CONTENT",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED when polaris.bootstrap.grants.privileges "
            "is a scalar string, but it succeeded. The schema must require a list "
            "of privilege strings.\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            f"helm template failed, but not due to schema validation.\nSTDERR: {stderr[:1000]}"
        )
        assert PRIVILEGES_FIELD in stderr_lower or "array" in stderr_lower, (
            "Schema validation failed, but the error does not reference the privileges "
            f"array constraint.\nSTDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.6")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_grants_invalid_privilege_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail when a grants privilege is unsupported."""
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.bootstrap.grants.privileges[0]=NOT_A_POLARIS_PRIVILEGE",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED when polaris.bootstrap.grants.privileges "
            "contains an unsupported privilege, but it succeeded. The schema must "
            "restrict privileges to known Polaris privilege names.\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            f"helm template failed, but not due to schema validation.\nSTDERR: {stderr[:1000]}"
        )
        assert PRIVILEGES_FIELD in stderr_lower or "enum" in stderr_lower, (
            "Schema validation failed, but the error does not reference the privileges "
            f"enum constraint.\nSTDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.6")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_valid_grants_configuration_succeeds(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST succeed with valid bootstrap grant settings."""
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.bootstrap.enabled=true",
                "polaris.auth.bootstrapCredentials.clientSecret=SCHEMA-TEST-SENTINEL",
                "polaris.bootstrap.grants.enabled=true",
                "polaris.bootstrap.grants.catalogRole=catalog_admin",
                "polaris.bootstrap.grants.principalRole=floe-pipeline",
                "polaris.bootstrap.grants.bootstrapPrincipal=root",
                "polaris.bootstrap.grants.privileges[0]=CATALOG_MANAGE_CONTENT",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with a valid Polaris bootstrap grants configuration. "
            "The schema should allow this configuration.\n"
            f"STDERR: {stderr[:1000]}"
        )

        stdout = _stdout_text(result)
        assert "apiVersion:" in stdout or "kind:" in stdout, (
            "helm template produced output but it does not contain K8s manifests."
        )

    @pytest.mark.requirement("AC-28.6")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_valid_long_grants_identity_names_succeed(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST not reject role names the bootstrap Job can render."""
        long_role_name = "platform_data_engineering_catalog_admin_role_for_customer_360_alpha"
        result = _helm_template(
            platform_chart_path,
            set_values=[
                "polaris.bootstrap.enabled=true",
                "polaris.auth.bootstrapCredentials.clientSecret=SCHEMA-TEST-SENTINEL",
                "polaris.bootstrap.grants.enabled=true",
                f"polaris.bootstrap.grants.catalogRole={long_role_name}",
                f"polaris.bootstrap.grants.principalRole={long_role_name}",
                f"polaris.bootstrap.grants.bootstrapPrincipal={long_role_name}",
                "polaris.bootstrap.grants.privileges[0]=CATALOG_MANAGE_CONTENT",
            ],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            "helm template FAILED with long but shell-safe Polaris grants identity "
            "names. The schema should not add a stricter maxLength cap than the "
            "bootstrap Job runtime validation.\n"
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
    "prod", "test", "demo"]. Any other value (typos like "production",
    random strings like "invalid", numeric strings, empty strings) MUST be
    rejected at install time via schema validation. This prevents silent
    misconfiguration where an operator deploys to a non-existent environment
    tier.
    """

    # -- Positive controls: each valid enum value MUST be accepted ----------

    @pytest.mark.requirement("AC-28.5")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    @pytest.mark.parametrize("env", VALID_ENVIRONMENTS)
    def test_valid_environment_accepted(
        self,
        platform_chart_path: Path,
        env: str,
    ) -> None:
        """Helm template MUST succeed with each valid environment enum value.

        The schema defines an enum of exactly 5 valid values. This parametrized
        test confirms every value in VALID_ENVIRONMENTS is accepted, catching
        partial enum definitions where a value is accidentally omitted.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=[f"global.environment={env}"],
        )

        stderr = _stderr_text(result)

        assert result.returncode == 0, (
            f"helm template FAILED with global.environment={env}. "
            f"'{env}' is a valid enum value and MUST be accepted.\n"
            f"STDERR: {stderr[:1000]}"
        )

        stdout = _stdout_text(result)
        assert "apiVersion:" in stdout or "kind:" in stdout, (
            f"helm template succeeded with global.environment={env} but "
            "output does not contain K8s manifests."
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
            "['dev', 'qa', 'staging', 'prod', 'test', 'demo'].\n"
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

    @pytest.mark.requirement("AC-28.5")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_uppercase_environment_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail with global.environment=DEV (case-sensitive enum).

        JSON Schema enum matching is case-sensitive. 'DEV' is not the same
        as 'dev'. This boundary test confirms that the schema does not
        silently accept case variations, which would defeat the purpose
        of the enum constraint.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=["global.environment=DEV"],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED with global.environment=DEV "
            "(uppercase), but it succeeded. The enum is case-sensitive and "
            "MUST only accept lowercase values.\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            "helm template failed with global.environment=DEV, but "
            "stderr does not indicate a schema validation error.\n"
            f"Expected one of: '{SCHEMA_ERROR_INDICATOR}', '{SCHEMA_VALIDATION_FAILED}'\n"
            f"STDERR: {stderr[:1000]}"
        )

    @pytest.mark.requirement("AC-28.5")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_empty_environment_rejected(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Helm template MUST fail with global.environment= (empty string).

        An empty string is not in the enum and must be rejected. This
        boundary test guards against a schema that accidentally includes
        an empty string in the enum list.
        """
        result = _helm_template(
            platform_chart_path,
            set_values=["global.environment="],
        )

        stderr = _stderr_text(result)

        assert result.returncode != 0, (
            "helm template should have FAILED with empty global.environment, "
            "but it succeeded. The enum must reject empty strings.\n"
            f"STDOUT (first 500 chars): {_stdout_text(result)[:500]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR in stderr_lower or SCHEMA_VALIDATION_FAILED in stderr_lower, (
            f"helm template failed, but not due to schema validation.\nSTDERR: {stderr[:1000]}"
        )


# ---------------------------------------------------------------------------
# Helper: helm lint
# ---------------------------------------------------------------------------


def _helm_lint(
    chart_path: Path,
    values_files: list[Path],
) -> subprocess.CompletedProcess[bytes]:
    """Run helm lint with the given values files.

    Args:
        chart_path: Absolute path to the Helm chart.
        values_files: List of values file paths to pass via --values flags.

    Returns:
        CompletedProcess with stdout, stderr, and returncode.
    """
    cmd: list[str] = [
        "helm",
        "lint",
        str(chart_path),
    ]
    for vf in values_files:
        cmd.extend(["--values", str(vf)])

    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=60,
        check=False,
    )


# ---------------------------------------------------------------------------
# AC-28.3: Both values files pass enhanced schema (regression prevention)
# ---------------------------------------------------------------------------


class TestValuesFilesPassSchema:
    """Tests that both values.yaml and values-test.yaml pass the enhanced schema.

    AC-28.3: ``helm lint`` passes with both ``values.yaml`` and
    ``values-test.yaml`` against the enhanced ``values.schema.json``.
    No regressions.  These tests are regression-prevention guards that
    ensure future schema changes do not accidentally invalidate the
    shipped values files.

    Each test verifies three things:
        1. Exit code is exactly 0 (lint succeeded).
        2. Stderr does NOT contain schema validation error indicators
           (catches cases where Helm logs a warning but still exits 0).
        3. Stdout contains meaningful output confirming the chart was
           actually processed (not a no-op due to a bad chart path).
    """

    @pytest.mark.requirement("AC-28.3")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_lint_passes_with_default_values(
        self,
        platform_chart_path: Path,
    ) -> None:
        """helm lint MUST exit 0 with the default values.yaml.

        values.yaml is the primary values file shipped with the chart.
        It defines defaults for all schema-constrained fields.  A schema
        that rejects the default values file is a broken schema.
        """
        values_file = platform_chart_path / "values.yaml"
        assert values_file.exists(), (
            f"values.yaml not found at {values_file}. Chart must ship a default values file."
        )

        result = _helm_lint(platform_chart_path, [values_file])
        stderr = _stderr_text(result)
        stdout = _stdout_text(result)

        assert result.returncode == 0, (
            "helm lint FAILED with the default values.yaml. "
            "The enhanced schema must accept the shipped default values.\n"
            f"STDERR: {stderr[:2000]}"
        )

        # Ensure no schema validation errors lurk in stderr despite exit 0
        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR not in stderr_lower, (
            "helm lint exited 0 but stderr contains schema validation "
            f"error text ('{SCHEMA_ERROR_INDICATOR}'). This indicates a "
            "partial failure that Helm did not surface via exit code.\n"
            f"STDERR: {stderr[:2000]}"
        )
        assert SCHEMA_VALIDATION_FAILED not in stderr_lower, (
            "helm lint exited 0 but stderr contains schema validation "
            f"failure text ('{SCHEMA_VALIDATION_FAILED}'). This indicates "
            "a partial failure that Helm did not surface via exit code.\n"
            f"STDERR: {stderr[:2000]}"
        )

        # Confirm the chart was actually processed (not a silent no-op)
        assert "linted" in stdout.lower(), (
            "helm lint exited 0 but stdout does not contain 'linted'. "
            "Expected a lint summary line confirming the chart was processed."
        )

    @pytest.mark.requirement("AC-28.3")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_lint_passes_with_test_values(
        self,
        platform_chart_path: Path,
    ) -> None:
        """helm lint MUST exit 0 with values-test.yaml.

        values-test.yaml provides overrides for CI and testing
        environments.  If the schema rejects it, the CI pipeline
        cannot deploy test environments.
        """
        values_file = platform_chart_path / "values-test.yaml"
        assert values_file.exists(), (
            f"values-test.yaml not found at {values_file}. "
            "Chart must include a test values override file."
        )

        result = _helm_lint(platform_chart_path, [values_file])
        stderr = _stderr_text(result)
        stdout = _stdout_text(result)

        assert result.returncode == 0, (
            "helm lint FAILED with values-test.yaml. "
            "The enhanced schema must accept the test values file.\n"
            f"STDERR: {stderr[:2000]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR not in stderr_lower, (
            "helm lint exited 0 but stderr contains schema validation "
            f"error text ('{SCHEMA_ERROR_INDICATOR}') when using "
            "values-test.yaml. Possible partial schema failure.\n"
            f"STDERR: {stderr[:2000]}"
        )
        assert SCHEMA_VALIDATION_FAILED not in stderr_lower, (
            "helm lint exited 0 but stderr contains schema validation "
            f"failure text ('{SCHEMA_VALIDATION_FAILED}') when using "
            "values-test.yaml.\n"
            f"STDERR: {stderr[:2000]}"
        )

        assert "linted" in stdout.lower(), (
            "helm lint exited 0 but stdout does not contain 'linted' for "
            "values-test.yaml. Expected a lint summary line."
        )

    @pytest.mark.requirement("AC-28.3")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_lint_passes_with_both_values_overlaid(
        self,
        platform_chart_path: Path,
    ) -> None:
        """helm lint MUST exit 0 with values-test.yaml overlaid on values.yaml.

        In real CI usage, operators apply ``--values values.yaml --values
        values-test.yaml`` so that test overrides merge on top of defaults.
        The merged result must also pass schema validation.  A schema that
        accepts each file individually but rejects the overlay has a
        constraint conflict (e.g., an if/then that the overlay violates).
        """
        base_values = platform_chart_path / "values.yaml"
        test_values = platform_chart_path / "values-test.yaml"
        assert base_values.exists(), f"values.yaml not found at {base_values}."
        assert test_values.exists(), f"values-test.yaml not found at {test_values}."

        result = _helm_lint(
            platform_chart_path,
            [base_values, test_values],
        )
        stderr = _stderr_text(result)
        stdout = _stdout_text(result)

        assert result.returncode == 0, (
            "helm lint FAILED with values-test.yaml overlaid on values.yaml. "
            "The merged configuration must satisfy the enhanced schema. "
            "This may indicate an if/then constraint conflict between the "
            "two files.\n"
            f"STDERR: {stderr[:2000]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR not in stderr_lower, (
            "helm lint exited 0 but stderr contains schema validation "
            f"error text ('{SCHEMA_ERROR_INDICATOR}') when overlaying "
            "values-test.yaml on values.yaml.\n"
            f"STDERR: {stderr[:2000]}"
        )
        assert SCHEMA_VALIDATION_FAILED not in stderr_lower, (
            "helm lint exited 0 but stderr contains schema validation "
            f"failure text ('{SCHEMA_VALIDATION_FAILED}') when overlaying "
            "values-test.yaml on values.yaml.\n"
            f"STDERR: {stderr[:2000]}"
        )

        assert "linted" in stdout.lower(), (
            "helm lint exited 0 but stdout does not contain 'linted' for "
            "overlaid values. Expected a lint summary line."
        )

    @pytest.mark.requirement("AC-28.3")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_lint_passes_with_reverse_overlay_order(
        self,
        platform_chart_path: Path,
    ) -> None:
        """helm lint MUST exit 0 with values.yaml overlaid on values-test.yaml.

        Helm applies values files left-to-right, with later files winning.
        Reversing the order (values-test.yaml first, then values.yaml)
        exercises a different merge result.  If the schema has conditional
        constraints (if/then), the winning values must satisfy them
        regardless of application order.
        """
        base_values = platform_chart_path / "values.yaml"
        test_values = platform_chart_path / "values-test.yaml"

        result = _helm_lint(
            platform_chart_path,
            [test_values, base_values],
        )
        stderr = _stderr_text(result)
        stdout = _stdout_text(result)

        assert result.returncode == 0, (
            "helm lint FAILED with values.yaml overlaid on values-test.yaml "
            "(reverse order). The schema must accept the merged result "
            "regardless of overlay application order.\n"
            f"STDERR: {stderr[:2000]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR not in stderr_lower, (
            "helm lint exited 0 but stderr contains schema validation "
            f"error text ('{SCHEMA_ERROR_INDICATOR}') with reverse "
            "overlay order.\n"
            f"STDERR: {stderr[:2000]}"
        )
        assert SCHEMA_VALIDATION_FAILED not in stderr_lower, (
            "helm lint exited 0 but stderr contains schema validation "
            f"failure text ('{SCHEMA_VALIDATION_FAILED}') with reverse "
            "overlay order.\n"
            f"STDERR: {stderr[:2000]}"
        )

        assert "linted" in stdout.lower(), (
            "helm lint exited 0 but stdout does not contain 'linted' for "
            "reverse overlay order. Expected a lint summary line."
        )

    @pytest.mark.requirement("AC-28.3")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_lint_with_default_values_no_explicit_file(
        self,
        platform_chart_path: Path,
    ) -> None:
        """helm lint MUST exit 0 with no explicit --values flag (uses chart defaults).

        When no --values flag is passed, Helm uses the chart's built-in
        values.yaml.  This is the simplest deployment path and must not
        be broken by schema enhancements.  This test catches the case
        where the _helm_lint helper or the chart path is misconfigured.
        """
        result = _helm_lint(platform_chart_path, [])
        stderr = _stderr_text(result)
        stdout = _stdout_text(result)

        assert result.returncode == 0, (
            "helm lint FAILED with no explicit values file (using chart "
            "defaults). The chart's built-in values.yaml must satisfy "
            "its own schema.\n"
            f"STDERR: {stderr[:2000]}"
        )

        stderr_lower = stderr.lower()
        assert SCHEMA_ERROR_INDICATOR not in stderr_lower, (
            "helm lint exited 0 but stderr contains schema validation "
            f"error text ('{SCHEMA_ERROR_INDICATOR}') when using chart "
            "defaults (no --values flag).\n"
            f"STDERR: {stderr[:2000]}"
        )
        assert SCHEMA_VALIDATION_FAILED not in stderr_lower, (
            "helm lint exited 0 but stderr contains schema validation "
            f"failure text ('{SCHEMA_VALIDATION_FAILED}') when using "
            "chart defaults.\n"
            f"STDERR: {stderr[:2000]}"
        )

        assert "linted" in stdout.lower(), (
            "helm lint exited 0 but stdout does not contain 'linted' with "
            "chart defaults. Expected a lint summary line."
        )
