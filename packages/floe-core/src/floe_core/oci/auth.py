"""Authentication providers for OCI registry operations.

This module implements the authentication provider interface for various
registry authentication methods as defined in the OCI Client spec (Epic 8A).

Supported Authentication Types:
- BasicAuthProvider: Username/password authentication (Harbor, self-hosted)
- TokenAuthProvider: Bearer token authentication (GitHub Packages, generic)
- IRSAAuthProvider: AWS IAM Role for Service Account (Amazon ECR)
- AzureMIAuthProvider: Azure Managed Identity (Azure ACR)
- GCPWIAuthProvider: GCP Workload Identity (Google Artifact Registry)

Authentication Flow:
    1. RegistryConfig specifies auth type and credentials reference
    2. AuthProvider resolves credentials via SecretsPlugin (for basic/token)
    3. Cloud providers use automatic credentials (IRSA, MI, WI)
    4. Credentials are cached and refreshed as needed

Example:
    >>> from floe_core.oci.auth import create_auth_provider
    >>> from floe_core.schemas.oci import RegistryConfig
    >>>
    >>> # Create auth provider from registry config
    >>> provider = create_auth_provider(registry_config, secrets_plugin)
    >>>
    >>> # Get credentials for ORAS client
    >>> creds = provider.get_credentials()
    >>> client.login(registry, creds.username, creds.password)

See Also:
    - specs/08a-oci-client/research.md: Authentication research
    - floe_core.plugins.secrets: SecretsPlugin ABC
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog

from floe_core.oci.errors import AuthenticationError
from floe_core.schemas.oci import AuthType, RegistryAuth

if TYPE_CHECKING:
    from floe_core.plugins.secrets import SecretsPlugin

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Credentials:
    """Container for registry credentials.

    Attributes:
        username: Username for basic auth (may be special value for cloud providers).
        password: Password or token for authentication.
        expires_at: Expiry time for token-based credentials (None if non-expiring).
    """

    username: str
    password: str
    expires_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        """Check if credentials have expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


class AuthProvider(ABC):
    """Abstract base class for OCI registry authentication providers.

    AuthProvider implementations are responsible for resolving and managing
    credentials for OCI registry operations. Each authentication type
    (basic, token, cloud providers) has its own implementation.

    Subclasses must implement:
        - get_credentials(): Retrieve current credentials
        - refresh_if_needed(): Refresh credentials if expired/expiring

    Example:
        >>> class MyAuthProvider(AuthProvider):
        ...     def get_credentials(self) -> Credentials:
        ...         return Credentials(username="user", password="pass")
        ...
        ...     def refresh_if_needed(self) -> bool:
        ...         return False  # Non-expiring credentials
    """

    @abstractmethod
    def get_credentials(self) -> Credentials:
        """Retrieve current credentials for registry authentication.

        Returns:
            Credentials object containing username/password.

        Raises:
            AuthenticationError: If credentials cannot be retrieved.
        """
        ...

    @abstractmethod
    def refresh_if_needed(self) -> bool:
        """Refresh credentials if expired or about to expire.

        Should refresh if credentials will expire within a buffer period
        (e.g., 5 minutes) to avoid mid-operation failures.

        Returns:
            True if credentials were refreshed, False otherwise.

        Raises:
            AuthenticationError: If refresh fails.
        """
        ...

    @property
    @abstractmethod
    def auth_type(self) -> AuthType:
        """Return the authentication type for this provider."""
        ...


class BasicAuthProvider(AuthProvider):
    """Authentication provider for basic username/password auth.

    Used for Harbor, self-hosted registries, and other registries
    that accept username/password authentication.

    Credentials are resolved via SecretsPlugin from a Kubernetes Secret
    or other secret store.

    Example:
        >>> provider = BasicAuthProvider(
        ...     registry_uri="oci://harbor.example.com/floe",
        ...     secrets_plugin=k8s_secrets,
        ...     secret_name="registry-creds"
        ... )
        >>> creds = provider.get_credentials()
        >>> creds.username
        'admin'
    """

    def __init__(
        self,
        registry_uri: str,
        secrets_plugin: SecretsPlugin,
        secret_name: str,
    ) -> None:
        """Initialize BasicAuthProvider.

        Args:
            registry_uri: OCI registry URI for error messages.
            secrets_plugin: SecretsPlugin for credential resolution.
            secret_name: Name of secret containing username/password.
        """
        self._registry_uri = registry_uri
        self._secrets_plugin = secrets_plugin
        self._secret_name = secret_name
        self._credentials: Credentials | None = None

    @property
    def auth_type(self) -> AuthType:
        """Return the authentication type."""
        return AuthType.BASIC

    def get_credentials(self) -> Credentials:
        """Retrieve credentials from SecretsPlugin.

        Expects secret to contain 'username' and 'password' keys.

        Returns:
            Credentials with username and password.

        Raises:
            AuthenticationError: If secret not found or missing required keys.
        """
        if self._credentials is not None:
            return self._credentials

        try:
            secret_data = self._secrets_plugin.get_multi_key_secret(self._secret_name)
        except NotImplementedError:
            # Fallback for plugins that don't support multi-key
            username = self._secrets_plugin.get_secret(f"{self._secret_name}/username")
            password = self._secrets_plugin.get_secret(f"{self._secret_name}/password")
            if username is None or password is None:
                raise AuthenticationError(
                    self._registry_uri,
                    f"Secret '{self._secret_name}' missing username or password",
                ) from None
            secret_data = {"username": username, "password": password}
        except Exception as e:
            raise AuthenticationError(
                self._registry_uri,
                f"Failed to retrieve secret '{self._secret_name}': {e}",
            ) from e

        username = secret_data.get("username")
        password = secret_data.get("password")

        if not username or not password:
            raise AuthenticationError(
                self._registry_uri,
                f"Secret '{self._secret_name}' missing required 'username' or 'password' keys",
            )

        self._credentials = Credentials(username=username, password=password)
        logger.debug(
            "basic_auth_credentials_loaded",
            registry=self._registry_uri,
            secret_name=self._secret_name,
        )
        return self._credentials

    def refresh_if_needed(self) -> bool:
        """Refresh not needed for basic auth (non-expiring)."""
        return False


class TokenAuthProvider(AuthProvider):
    """Authentication provider for bearer token auth.

    Used for GitHub Packages, GitLab Container Registry, and other
    registries that accept bearer tokens.

    Credentials are resolved via SecretsPlugin from a Kubernetes Secret
    or other secret store.

    Example:
        >>> provider = TokenAuthProvider(
        ...     registry_uri="oci://ghcr.io/myorg",
        ...     secrets_plugin=k8s_secrets,
        ...     secret_name="ghcr-token"
        ... )
        >>> creds = provider.get_credentials()
        >>> creds.username  # Special username for token auth
        '__token__'
    """

    # Special username for token-based authentication
    TOKEN_USERNAME = "__token__"

    def __init__(
        self,
        registry_uri: str,
        secrets_plugin: SecretsPlugin,
        secret_name: str,
    ) -> None:
        """Initialize TokenAuthProvider.

        Args:
            registry_uri: OCI registry URI for error messages.
            secrets_plugin: SecretsPlugin for credential resolution.
            secret_name: Name of secret containing token.
        """
        self._registry_uri = registry_uri
        self._secrets_plugin = secrets_plugin
        self._secret_name = secret_name
        self._credentials: Credentials | None = None

    @property
    def auth_type(self) -> AuthType:
        """Return the authentication type."""
        return AuthType.TOKEN

    def get_credentials(self) -> Credentials:
        """Retrieve token from SecretsPlugin.

        Expects secret to contain 'token' key (or be a single-value secret).

        Returns:
            Credentials with special username and token as password.

        Raises:
            AuthenticationError: If secret not found.
        """
        if self._credentials is not None:
            return self._credentials

        token: str | None = None
        try:
            # Try multi-key first (secret may have 'token' key)
            secret_data = self._secrets_plugin.get_multi_key_secret(self._secret_name)
            token = secret_data.get("token")
        except NotImplementedError:
            # Fallback to single key
            pass
        except Exception as e:
            raise AuthenticationError(
                self._registry_uri,
                f"Failed to retrieve secret '{self._secret_name}': {e}",
            ) from e

        if token is None:
            # Try direct key lookup
            token = self._secrets_plugin.get_secret(self._secret_name)
            if token is None:
                token = self._secrets_plugin.get_secret(f"{self._secret_name}/token")

        if not token:
            raise AuthenticationError(
                self._registry_uri,
                f"Secret '{self._secret_name}' missing token value",
            )

        self._credentials = Credentials(username=self.TOKEN_USERNAME, password=token)
        logger.debug(
            "token_auth_credentials_loaded",
            registry=self._registry_uri,
            secret_name=self._secret_name,
        )
        return self._credentials

    def refresh_if_needed(self) -> bool:
        """Refresh not needed for static tokens (non-expiring)."""
        return False


class IRSAAuthProvider(AuthProvider):
    """Authentication provider for AWS IAM Role for Service Account (IRSA).

    Used for Amazon ECR. Credentials are obtained automatically via
    IAM role attached to the Kubernetes service account.

    Note: Requires boto3 at runtime for ECR token retrieval.

    Example:
        >>> provider = IRSAAuthProvider(
        ...     registry_uri="oci://123456789.dkr.ecr.us-east-1.amazonaws.com/floe"
        ... )
        >>> creds = provider.get_credentials()
        >>> creds.username
        'AWS'
    """

    # ECR tokens expire after 12 hours
    TOKEN_LIFETIME_HOURS = 12
    # Refresh 30 minutes before expiry
    REFRESH_BUFFER_MINUTES = 30

    def __init__(self, registry_uri: str) -> None:
        """Initialize IRSAAuthProvider.

        Args:
            registry_uri: OCI registry URI (ECR format).
        """
        self._registry_uri = registry_uri
        self._credentials: Credentials | None = None

    @property
    def auth_type(self) -> AuthType:
        """Return the authentication type."""
        return AuthType.AWS_IRSA

    def get_credentials(self) -> Credentials:
        """Retrieve ECR auth token via IRSA.

        Uses boto3 to get an ECR authorization token using the IAM role
        attached to the service account.

        Returns:
            Credentials with 'AWS' username and ECR token as password.

        Raises:
            AuthenticationError: If token retrieval fails.
        """
        if self._credentials is not None and not self._should_refresh():
            return self._credentials

        try:
            import boto3
        except ImportError as e:
            raise AuthenticationError(
                self._registry_uri,
                "boto3 required for AWS IRSA auth. Install with: pip install boto3",
            ) from e

        try:
            # Extract region from ECR URI
            region = self._extract_region()
            ecr_client = boto3.client("ecr", region_name=region)
            response = ecr_client.get_authorization_token()

            auth_data = response["authorizationData"][0]
            # Token is base64 encoded "username:password"
            import base64

            token = base64.b64decode(auth_data["authorizationToken"]).decode("utf-8")
            username, password = token.split(":", 1)

            expires_at = auth_data.get("expiresAt")
            if isinstance(expires_at, datetime):
                # Ensure timezone-aware
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

            self._credentials = Credentials(
                username=username,
                password=password,
                expires_at=expires_at,
            )

            logger.debug(
                "irsa_credentials_obtained",
                registry=self._registry_uri,
                expires_at=expires_at.isoformat() if expires_at else None,
            )
            return self._credentials

        except Exception as e:
            raise AuthenticationError(
                self._registry_uri,
                f"Failed to get ECR authorization token: {e}",
            ) from e

    def refresh_if_needed(self) -> bool:
        """Refresh credentials if near expiry.

        Refreshes if credentials will expire within REFRESH_BUFFER_MINUTES.

        Returns:
            True if credentials were refreshed, False otherwise.
        """
        if not self._should_refresh():
            return False

        # Clear cached credentials and re-fetch
        self._credentials = None
        self.get_credentials()
        return True

    def _should_refresh(self) -> bool:
        """Check if credentials should be refreshed."""
        if self._credentials is None:
            return True
        if self._credentials.expires_at is None:
            return False

        buffer = timedelta(minutes=self.REFRESH_BUFFER_MINUTES)
        return datetime.now(timezone.utc) > (self._credentials.expires_at - buffer)

    def _extract_region(self) -> str:
        """Extract AWS region from ECR URI.

        ECR URI format: oci://123456789.dkr.ecr.REGION.amazonaws.com/repo

        Returns:
            AWS region string.

        Raises:
            AuthenticationError: If region cannot be extracted.
        """
        # Remove oci:// prefix
        uri = self._registry_uri.replace("oci://", "")
        parts = uri.split(".")
        # Expected: [account_id, 'dkr', 'ecr', REGION, 'amazonaws', 'com', ...]
        if len(parts) >= 4 and parts[1] == "dkr" and parts[2] == "ecr":
            return parts[3]
        raise AuthenticationError(
            self._registry_uri,
            "Cannot extract AWS region from ECR URI",
        )


class AzureMIAuthProvider(AuthProvider):
    """Authentication provider for Azure Managed Identity.

    Used for Azure Container Registry. Credentials are obtained automatically
    via the managed identity attached to the Azure resource.

    Note: Requires azure-identity at runtime.

    Example:
        >>> provider = AzureMIAuthProvider(
        ...     registry_uri="oci://myregistry.azurecr.io/floe"
        ... )
        >>> creds = provider.get_credentials()
    """

    # Azure tokens typically expire after 1 hour
    REFRESH_BUFFER_MINUTES = 10

    def __init__(self, registry_uri: str) -> None:
        """Initialize AzureMIAuthProvider.

        Args:
            registry_uri: OCI registry URI (ACR format).
        """
        self._registry_uri = registry_uri
        self._credentials: Credentials | None = None

    @property
    def auth_type(self) -> AuthType:
        """Return the authentication type."""
        return AuthType.AZURE_MANAGED_IDENTITY

    def get_credentials(self) -> Credentials:
        """Retrieve ACR token via Azure Managed Identity.

        Returns:
            Credentials with special username and ACR refresh token.

        Raises:
            AuthenticationError: If token retrieval fails.
        """
        if self._credentials is not None and not self._should_refresh():
            return self._credentials

        try:
            from azure.identity import DefaultAzureCredential
        except ImportError as e:
            raise AuthenticationError(
                self._registry_uri,
                "azure-identity required for Azure MI auth. "
                "Install with: pip install azure-identity",
            ) from e

        try:
            credential = DefaultAzureCredential()
            # ACR scope for token exchange
            token = credential.get_token("https://management.azure.com/.default")

            expires_at = datetime.fromtimestamp(token.expires_on, tz=timezone.utc)

            # ACR uses special username for token-based auth
            self._credentials = Credentials(
                username="00000000-0000-0000-0000-000000000000",
                password=token.token,
                expires_at=expires_at,
            )

            logger.debug(
                "azure_mi_credentials_obtained",
                registry=self._registry_uri,
                expires_at=expires_at.isoformat(),
            )
            return self._credentials

        except Exception as e:
            raise AuthenticationError(
                self._registry_uri,
                f"Failed to get Azure token: {e}",
            ) from e

    def refresh_if_needed(self) -> bool:
        """Refresh credentials if near expiry."""
        if not self._should_refresh():
            return False

        self._credentials = None
        self.get_credentials()
        return True

    def _should_refresh(self) -> bool:
        """Check if credentials should be refreshed."""
        if self._credentials is None:
            return True
        if self._credentials.expires_at is None:
            return False

        buffer = timedelta(minutes=self.REFRESH_BUFFER_MINUTES)
        return datetime.now(timezone.utc) > (self._credentials.expires_at - buffer)


class GCPWIAuthProvider(AuthProvider):
    """Authentication provider for GCP Workload Identity.

    Used for Google Artifact Registry. Credentials are obtained automatically
    via workload identity federation.

    Note: Requires google-auth at runtime.

    Example:
        >>> provider = GCPWIAuthProvider(
        ...     registry_uri="oci://us-central1-docker.pkg.dev/my-project/my-repo"
        ... )
        >>> creds = provider.get_credentials()
    """

    # GCP tokens expire after 1 hour
    REFRESH_BUFFER_MINUTES = 10

    def __init__(self, registry_uri: str) -> None:
        """Initialize GCPWIAuthProvider.

        Args:
            registry_uri: OCI registry URI (Artifact Registry format).
        """
        self._registry_uri = registry_uri
        self._credentials: Credentials | None = None

    @property
    def auth_type(self) -> AuthType:
        """Return the authentication type."""
        return AuthType.GCP_WORKLOAD_IDENTITY

    def get_credentials(self) -> Credentials:
        """Retrieve GAR token via GCP Workload Identity.

        Returns:
            Credentials with 'oauth2accesstoken' username and access token.

        Raises:
            AuthenticationError: If token retrieval fails.
        """
        if self._credentials is not None and not self._should_refresh():
            return self._credentials

        try:
            import google.auth  # type: ignore[import-untyped]
            from google.auth.transport.requests import (  # type: ignore[import-untyped]
                Request,
            )
        except ImportError as e:
            raise AuthenticationError(
                self._registry_uri,
                "google-auth required for GCP WI auth. "
                "Install with: pip install google-auth",
            ) from e

        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(Request())

            expires_at = None
            if hasattr(credentials, "expiry") and credentials.expiry:
                expires_at = credentials.expiry
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

            self._credentials = Credentials(
                username="oauth2accesstoken",
                password=credentials.token,
                expires_at=expires_at,
            )

            logger.debug(
                "gcp_wi_credentials_obtained",
                registry=self._registry_uri,
                expires_at=expires_at.isoformat() if expires_at else None,
            )
            return self._credentials

        except Exception as e:
            raise AuthenticationError(
                self._registry_uri,
                f"Failed to get GCP token: {e}",
            ) from e

    def refresh_if_needed(self) -> bool:
        """Refresh credentials if near expiry."""
        if not self._should_refresh():
            return False

        self._credentials = None
        self.get_credentials()
        return True

    def _should_refresh(self) -> bool:
        """Check if credentials should be refreshed."""
        if self._credentials is None:
            return True
        if self._credentials.expires_at is None:
            return False

        buffer = timedelta(minutes=self.REFRESH_BUFFER_MINUTES)
        return datetime.now(timezone.utc) > (self._credentials.expires_at - buffer)


def create_auth_provider(
    registry_uri: str,
    auth_config: RegistryAuth,
    secrets_plugin: SecretsPlugin | None = None,
) -> AuthProvider:
    """Factory function to create appropriate auth provider.

    Creates an AuthProvider instance based on the auth type configured
    in RegistryAuth.

    Args:
        registry_uri: OCI registry URI.
        auth_config: Authentication configuration from RegistryConfig.
        secrets_plugin: SecretsPlugin for basic/token auth credential resolution.

    Returns:
        AuthProvider instance for the configured auth type.

    Raises:
        AuthenticationError: If required secrets_plugin not provided for basic/token auth.
        ValueError: If auth type is unknown.

    Example:
        >>> provider = create_auth_provider(
        ...     "oci://harbor.example.com/floe",
        ...     RegistryAuth(type=AuthType.BASIC, credentials_ref=ref),
        ...     secrets_plugin=k8s_secrets
        ... )
    """
    auth_type = auth_config.type

    if auth_type == AuthType.BASIC:
        if secrets_plugin is None:
            raise AuthenticationError(
                registry_uri, "SecretsPlugin required for basic auth"
            )
        if auth_config.credentials_ref is None:
            raise AuthenticationError(
                registry_uri, "credentials_ref required for basic auth"
            )
        return BasicAuthProvider(
            registry_uri=registry_uri,
            secrets_plugin=secrets_plugin,
            secret_name=auth_config.credentials_ref.name,
        )

    if auth_type == AuthType.TOKEN:
        if secrets_plugin is None:
            raise AuthenticationError(
                registry_uri, "SecretsPlugin required for token auth"
            )
        if auth_config.credentials_ref is None:
            raise AuthenticationError(
                registry_uri, "credentials_ref required for token auth"
            )
        return TokenAuthProvider(
            registry_uri=registry_uri,
            secrets_plugin=secrets_plugin,
            secret_name=auth_config.credentials_ref.name,
        )

    if auth_type == AuthType.AWS_IRSA:
        return IRSAAuthProvider(registry_uri=registry_uri)

    if auth_type == AuthType.AZURE_MANAGED_IDENTITY:
        return AzureMIAuthProvider(registry_uri=registry_uri)

    if auth_type == AuthType.GCP_WORKLOAD_IDENTITY:
        return GCPWIAuthProvider(registry_uri=registry_uri)

    raise ValueError(f"Unknown auth type: {auth_type}")
