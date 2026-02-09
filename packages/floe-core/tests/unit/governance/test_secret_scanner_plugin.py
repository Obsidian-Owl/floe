"""Unit tests for SecretScannerPlugin ABC (Task T015).

These tests verify the SecretScannerPlugin abstract base class compliance.
Written before implementation (TDD) - tests will fail until T018 implements the ABC.

Requirements:
    - 3E-FR-009: SecretScannerPlugin ABC with scan_file, scan_directory, get_supported_patterns
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_core.governance.types import SecretFinding


@pytest.mark.requirement("3E-FR-009")
def test_secret_scanner_plugin_is_abstract() -> None:
    """Test that SecretScannerPlugin cannot be instantiated directly.

    Verifies that SecretScannerPlugin is an abstract base class that requires
    implementation of abstract methods before instantiation.
    """
    from floe_core.plugins.secret_scanner import (
        SecretScannerPlugin,
    )

    with pytest.raises(TypeError, match="abstract"):
        SecretScannerPlugin()  # Will fail until implementation exists (TDD)


@pytest.mark.requirement("3E-FR-009")
def test_secret_scanner_plugin_inherits_plugin_metadata() -> None:
    """Test that SecretScannerPlugin inherits from PluginMetadata.

    Verifies that SecretScannerPlugin is a subclass of the PluginMetadata ABC,
    ensuring consistent plugin interface across all floe plugin types.
    """
    from floe_core.plugin_metadata import PluginMetadata
    from floe_core.plugins.secret_scanner import (
        SecretScannerPlugin,
    )

    assert issubclass(SecretScannerPlugin, PluginMetadata), (
        "SecretScannerPlugin must inherit from PluginMetadata"
    )


@pytest.mark.requirement("3E-FR-009")
def test_scan_file_is_abstract_method() -> None:
    """Test that scan_file is an abstract method.

    Verifies that scan_file must be implemented by concrete subclasses.
    """
    from floe_core.plugins.secret_scanner import (
        SecretScannerPlugin,
    )

    # Check that scan_file is in abstract methods
    abstract_methods: set[str] = getattr(SecretScannerPlugin, "__abstractmethods__", set())
    assert "scan_file" in abstract_methods, "scan_file must be an abstract method"


@pytest.mark.requirement("3E-FR-009")
def test_scan_directory_is_abstract_method() -> None:
    """Test that scan_directory is an abstract method.

    Verifies that scan_directory must be implemented by concrete subclasses.
    """
    from floe_core.plugins.secret_scanner import (
        SecretScannerPlugin,
    )

    # Check that scan_directory is in abstract methods
    abstract_methods: set[str] = getattr(SecretScannerPlugin, "__abstractmethods__", set())
    assert "scan_directory" in abstract_methods, "scan_directory must be an abstract method"


@pytest.mark.requirement("3E-FR-009")
def test_get_supported_patterns_is_abstract_method() -> None:
    """Test that get_supported_patterns is an abstract method.

    Verifies that get_supported_patterns must be implemented by concrete subclasses.
    """
    from floe_core.plugins.secret_scanner import (
        SecretScannerPlugin,
    )

    # Check that get_supported_patterns is in abstract methods
    abstract_methods: set[str] = getattr(SecretScannerPlugin, "__abstractmethods__", set())
    assert "get_supported_patterns" in abstract_methods, (
        "get_supported_patterns must be an abstract method"
    )


@pytest.mark.requirement("3E-FR-009")
def test_concrete_implementation_requires_all_methods() -> None:
    """Test that incomplete implementations cannot be instantiated.

    Verifies that a concrete class missing abstract methods cannot be instantiated.
    """
    from floe_core.plugins.secret_scanner import (
        SecretScannerPlugin,
    )

    class IncompleteScanner(SecretScannerPlugin):  # type: ignore[misc]
        """Incomplete implementation missing abstract methods."""

        @property
        def name(self) -> str:
            return "incomplete"

        @property
        def version(self) -> str:
            return "1.0.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0.0"

        # Missing: scan_file, scan_directory, get_supported_patterns

    with pytest.raises(TypeError, match="abstract"):
        IncompleteScanner()  # Will fail until implementation exists (TDD)


@pytest.mark.requirement("3E-FR-009")
def test_concrete_implementation_works() -> None:
    """Test that complete implementations can be instantiated and methods work.

    Verifies that a concrete class implementing all abstract methods can be
    instantiated and that the methods have the correct signatures.
    """
    from floe_core.plugins.secret_scanner import (
        SecretScannerPlugin,
    )

    class ConcreteScanner(SecretScannerPlugin):  # type: ignore[misc]
        """Complete implementation of SecretScannerPlugin."""

        @property
        def name(self) -> str:
            return "test_scanner"

        @property
        def version(self) -> str:
            return "1.0.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0.0"

        def scan_file(self, file_path: Path, content: str) -> list[SecretFinding]:
            """Test implementation of scan_file."""
            return []

        def scan_directory(
            self,
            directory: Path,
            exclude_patterns: list[str] | None = None,
        ) -> list[SecretFinding]:
            """Test implementation of scan_directory."""
            return []

        def get_supported_patterns(self) -> list[str]:
            """Test implementation of get_supported_patterns."""
            return ["test_pattern"]

    # Should instantiate successfully
    scanner = ConcreteScanner()
    assert scanner.name == "test_scanner"
    assert scanner.version == "1.0.0"

    # Test method signatures work
    findings = scanner.scan_file(Path("test.py"), "content")
    assert isinstance(findings, list)

    findings = scanner.scan_directory(Path("."))
    assert isinstance(findings, list)

    patterns = scanner.get_supported_patterns()
    assert isinstance(patterns, list)
    assert "test_pattern" in patterns
