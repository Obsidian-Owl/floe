"""Secret reference models for manifest schema.

This module provides models for referencing secrets without exposing values.
Secrets remain as placeholders until runtime resolution.

Implements:
    - FR-010: Secret Reference Handling

Note:
    This module uses SecretReference (name + source pattern) for manifest-level
    secret declarations. The actual secret values are NEVER stored in manifests.

    When implementing runtime credential resolution in future components
    (e.g., floe-cli credential injection, CompiledArtifacts credential field),
    use Pydantic's SecretStr type to prevent accidental logging of secret values:

    Example for runtime handling::

        from pydantic import SecretStr

        class ResolvedCredentials(BaseModel):
            password: SecretStr  # SecretStr masks value in repr/str

        resolved = ResolvedCredentials(password="actual-secret")
        print(resolved)  # password=SecretStr('**********')
        actual_value = resolved.password.get_secret_value()

    See also: pydantic.SecretStr, pydantic.SecretBytes
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class SecretSource(str, Enum):
    """Secret backend source for credential resolution.

    Defines where secrets are stored and how they should be resolved at runtime.
    The manifest schema only validates the reference format - actual resolution
    happens at deployment time.

    Attributes:
        ENV: Environment variable (e.g., DATABASE_PASSWORD)
        KUBERNETES: Kubernetes Secret (default for K8s-native deployments)
        VAULT: HashiCorp Vault secret
        EXTERNAL_SECRETS: External Secrets Operator (ESO)
        INFISICAL: Infisical secrets manager (recommended OSS per ADR-0031)

    Example:
        >>> ref = SecretReference(source=SecretSource.KUBERNETES, name="db-creds")
        >>> ref.source.value
        'kubernetes'
    """

    ENV = "env"
    KUBERNETES = "kubernetes"
    VAULT = "vault"
    EXTERNAL_SECRETS = "external-secrets"
    INFISICAL = "infisical"


# Pattern for valid secret names (lowercase alphanumeric with hyphens)
SECRET_NAME_PATTERN = r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$"


class SecretReference(BaseModel):
    """Placeholder for sensitive values that references a secret by name.

    SecretReference acts as a pointer to credentials stored in a secret backend.
    The actual secret value is never stored in the manifest - only the reference.
    Resolution happens at runtime based on the configured secret backend.

    Attributes:
        source: Secret backend (env, kubernetes, vault, external-secrets)
        name: Secret name (lowercase alphanumeric with hyphens)
        key: Optional key within the secret (for multi-value secrets)

    Example:
        >>> ref = SecretReference(name="polaris-credentials")
        >>> ref.source
        <SecretSource.KUBERNETES: 'kubernetes'>

        >>> ref = SecretReference(
        ...     source=SecretSource.VAULT,
        ...     name="database-creds",
        ...     key="password"
        ... )

    See Also:
        - data-model.md: SecretReference entity specification
        - quickstart.md: Secret reference usage patterns
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"name": "polaris-credentials"},
                {"source": "vault", "name": "db-creds", "key": "password"},
            ]
        },
    )

    source: SecretSource = Field(
        default=SecretSource.KUBERNETES,
        description="Secret backend source",
    )
    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=253,  # K8s Secret name limit
            pattern=SECRET_NAME_PATTERN,
            description="Secret name (lowercase alphanumeric with hyphens)",
            examples=["polaris-credentials", "db-password"],
        ),
    ]
    key: str | None = Field(
        default=None,
        description="Key within secret for multi-value secrets",
    )

    def to_env_var_syntax(self) -> str:
        """Convert to dbt-compatible environment variable syntax.

        Returns a string that can be used in dbt profiles.yml to reference
        the secret via environment variable interpolation.

        Returns:
            String in format suitable for dbt env_var() macro.

        Example:
            >>> ref = SecretReference(name="db-password", key="value")
            >>> ref.to_env_var_syntax()
            "{{ env_var('FLOE_SECRET_DB_PASSWORD_VALUE') }}"
        """
        # Convert secret name to env var format (uppercase, underscores)
        env_name = self.name.upper().replace("-", "_")
        if self.key:
            key_suffix = self.key.upper().replace("-", "_")
            env_name = f"{env_name}_{key_suffix}"
        return f"{{{{ env_var('FLOE_SECRET_{env_name}') }}}}"

    def to_env_var_name(self) -> str:
        """Get the environment variable name (without dbt syntax).

        Returns the raw environment variable name that would be used
        at runtime to resolve this secret. Useful for K8s env injection.

        Returns:
            Environment variable name in format FLOE_SECRET_{NAME}_{KEY}.

        Example:
            >>> ref = SecretReference(name="db-creds", key="password")
            >>> ref.to_env_var_name()
            'FLOE_SECRET_DB_CREDS_PASSWORD'
        """
        env_name = self.name.upper().replace("-", "_")
        if self.key:
            key_suffix = self.key.upper().replace("-", "_")
            env_name = f"{env_name}_{key_suffix}"
        return f"FLOE_SECRET_{env_name}"


def resolve_secret_references(
    config: dict[str, Any],
) -> dict[str, Any]:
    """Resolve all SecretReference objects to env_var syntax in a config dict.

    Recursively walks the configuration dictionary and replaces any
    SecretReference instances with their dbt-compatible env_var() syntax.
    This is used during compilation to generate profiles.yml.

    Args:
        config: Configuration dictionary potentially containing SecretReference.

    Returns:
        New dictionary with SecretReferences replaced by env_var strings.

    Example:
        >>> config = {
        ...     "host": "localhost",
        ...     "password": SecretReference(name="db-creds", key="password"),
        ... }
        >>> resolved = resolve_secret_references(config)
        >>> resolved["password"]
        "{{ env_var('FLOE_SECRET_DB_CREDS_PASSWORD') }}"

    See Also:
        - T039: Compiler integration for profiles.yml generation
    """
    result: dict[str, Any] = {}

    for key, value in config.items():
        if isinstance(value, SecretReference):
            result[key] = value.to_env_var_syntax()
        elif isinstance(value, dict):
            result[key] = resolve_secret_references(value)
        elif isinstance(value, list):
            result[key] = [
                resolve_secret_references(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


# Patterns that indicate potential secrets in values
# These are checked during validation to prevent accidental secret exposure
SECRET_VALUE_PATTERNS = frozenset(
    {
        # Common secret prefixes
        "sk-",  # Stripe keys
        "pk-",  # Stripe keys
        "api_",  # API keys
        "key_",  # API keys
        "token_",  # Tokens
        "secret_",  # Generic secrets
        # Common encoding patterns
        "-----BEGIN",  # PEM certificates/keys
        "eyJ",  # Base64-encoded JWT
    }
)


def validate_no_secrets_in_artifacts(
    artifacts_dict: dict[str, Any],
    *,
    check_patterns: bool = True,
    additional_patterns: frozenset[str] | None = None,
) -> list[str]:
    """Validate that no raw secrets appear in compiled artifacts.

    Scans the artifacts dictionary for values that appear to be secrets
    (based on patterns like "sk-", "-----BEGIN", base64 JWT, etc.).

    This validation is run at the end of compilation to ensure SC-004:
    Zero secrets appear in floe compile output.

    Args:
        artifacts_dict: Serialized CompiledArtifacts as dictionary.
        check_patterns: Whether to check for secret-like patterns.
        additional_patterns: Additional patterns to check for.

    Returns:
        List of warning messages for potential secrets found.
        Empty list means validation passed.

    Example:
        >>> artifacts = {"dbt_profiles": {"password": "secret123"}}
        >>> warnings = validate_no_secrets_in_artifacts(artifacts)
        >>> # warnings would contain message about suspicious value

    Raises:
        No exceptions - returns warnings for the caller to handle.

    See Also:
        - SC-004: Zero secrets in floe compile output
        - T040: Validation implementation
    """
    warnings_list: list[str] = []
    patterns = SECRET_VALUE_PATTERNS
    if additional_patterns:
        patterns = patterns | additional_patterns

    def check_value(value: Any, path: str) -> None:
        """Recursively check a value for secret patterns."""
        if isinstance(value, str):
            # Skip env_var() references - these are expected
            if "env_var(" in value:
                return

            # Check for suspicious patterns
            if check_patterns:
                for pattern in patterns:
                    if value.startswith(pattern):
                        warnings_list.append(
                            f"Potential secret at '{path}': "
                            f"value starts with suspicious pattern '{pattern}...'"
                        )
                        break

        elif isinstance(value, dict):
            for k, v in value.items():
                check_value(v, f"{path}.{k}")

        elif isinstance(value, list):
            for i, item in enumerate(value):
                check_value(item, f"{path}[{i}]")

    # Start checking from root
    for key, value in artifacts_dict.items():
        check_value(value, key)

    return warnings_list


__all__ = [
    "SecretSource",
    "SecretReference",
    "SECRET_NAME_PATTERN",
    "SECRET_VALUE_PATTERNS",
    "resolve_secret_references",
    "validate_no_secrets_in_artifacts",
]
