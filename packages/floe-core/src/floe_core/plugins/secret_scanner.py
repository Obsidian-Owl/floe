"""SecretScannerPlugin ABC for secret detection plugins.

This module defines the abstract base class for secret scanning plugins that
detect hardcoded secrets, credentials, and sensitive data patterns in source
code and configuration files. The built-in regex scanner serves as the default;
external tools (Gitleaks, TruffleHog) integrate via this interface.

Entry point group: floe.secret_scanners

Example:
    >>> from floe_core.plugins.secret_scanner import SecretScannerPlugin
    >>> class GitleaksPlugin(SecretScannerPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "gitleaks"
    ...     # ... implement other abstract methods

Contract: See specs/3e-governance-integration/contracts/secret-scanner-plugin-contract.md
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from floe_core.plugin_metadata import PluginMetadata

if TYPE_CHECKING:
    from pathlib import Path

    from floe_core.governance.types import SecretFinding


class SecretScannerPlugin(PluginMetadata):
    """Abstract base class for secret scanning plugins.

    SecretScannerPlugin extends PluginMetadata with methods for detecting
    hardcoded secrets in source code and configuration files. Implementations
    scan files for patterns matching credentials, API keys, private keys,
    and other sensitive data.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - scan_file() method
        - scan_directory() method
        - get_supported_patterns() method

    Entry Point Group: floe.secret_scanners

    Example:
        >>> class GitleaksPlugin(SecretScannerPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "gitleaks"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def scan_file(self, file_path, content):
        ...         return self._run_gitleaks(file_path, content)

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - specs/3e-governance-integration/contracts/secret-scanner-plugin-contract.md
    """

    @abstractmethod
    def scan_file(self, file_path: Path, content: str) -> list[SecretFinding]:
        """Scan a single file for secrets.

        Args:
            file_path: Path to the file being scanned.
            content: File content to scan.

        Returns:
            List of secret findings in this file.
        """
        ...

    @abstractmethod
    def scan_directory(
        self,
        directory: Path,
        exclude_patterns: list[str] | None = None,
    ) -> list[SecretFinding]:
        """Scan a directory tree for secrets.

        Args:
            directory: Root directory to scan.
            exclude_patterns: Glob patterns to exclude from scanning.

        Returns:
            List of secret findings across all scanned files.
        """
        ...

    @abstractmethod
    def get_supported_patterns(self) -> list[str]:
        """Return names of patterns this scanner detects.

        Returns:
            List of pattern names (e.g., ["aws_access_key", "private_key"]).
        """
        ...
