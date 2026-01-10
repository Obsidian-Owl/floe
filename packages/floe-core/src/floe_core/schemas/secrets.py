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
from typing import Annotated

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

    Example:
        >>> ref = SecretReference(source=SecretSource.KUBERNETES, name="db-creds")
        >>> ref.source.value
        'kubernetes'
    """

    ENV = "env"
    KUBERNETES = "kubernetes"
    VAULT = "vault"
    EXTERNAL_SECRETS = "external-secrets"


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


__all__ = [
    "SecretSource",
    "SecretReference",
    "SECRET_NAME_PATTERN",
]
