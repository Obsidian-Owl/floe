"""Root-level test configuration for floe.

This conftest.py provides shared fixtures and configuration for all
root-level tests (contract tests, e2e tests).

Note:
    Root-level tests are for cross-package contracts and full platform
    workflows. Package-specific tests belong in their respective
    packages/*/tests/ directories.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


# Early PYTHONPATH check for better error messages
def _check_test_environment() -> None:
    """Verify tests are run from correct directory with proper PYTHONPATH."""
    try:
        import floe_core as _fc
    except ImportError:
        # Check if we're in a subdirectory
        cwd = Path.cwd()
        if cwd.name in ("floe-core", "packages", "plugins"):
            raise ImportError(
                f"Tests must be run from the repository root, not from {cwd}.\n"
                f"Run: cd {cwd.parent} && pytest tests/\n"
                "Or use: PYTHONPATH=. pytest tests/"
            ) from None
        raise ImportError(
            "floe_core not found. Ensure you're running from the repository root.\n"
            "Run: cd /path/to/floe && pytest tests/"
        ) from None
    # Verify module is importable
    _ = _fc.__name__


_check_test_environment()

import pytest  # noqa: E402
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION  # noqa: E402


@pytest.fixture
def compiled_artifacts_version() -> str:
    """Current CompiledArtifacts schema version.

    Tests should use this fixture instead of hardcoding version strings.
    When the schema version changes, all tests automatically adapt.

    Returns:
        Current version string (e.g., "0.3.0").

    Example:
        >>> def test_version_matches_schema(compiled_artifacts_version):
        ...     assert compiled_artifacts_version == "0.3.0"
    """
    return COMPILED_ARTIFACTS_VERSION


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Path to the repository root.

    Returns:
        Path to the root of the floe repository.
    """
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def compiled_artifacts() -> Callable[[Path], Any]:
    """Factory fixture that compiles floe.yaml through the real 6-stage pipeline.

    Uses the real compile_pipeline() function from floe-core, ensuring tests
    validate actual compilation behavior rather than hand-crafted test doubles.

    Returns:
        Factory function that compiles specs via the real compiler.

    Example:
        artifacts = compiled_artifacts(Path("demo/customer-360/floe.yaml"))
        assert artifacts.version == "0.5.0"
    """
    from floe_core.compilation.stages import compile_pipeline

    root = Path(__file__).parent.parent
    manifest_path = root / "demo" / "manifest.yaml"

    def _compile_artifacts(spec_path: Path) -> Any:
        """Compile floe.yaml to CompiledArtifacts via real 6-stage pipeline.

        Args:
            spec_path: Path to floe.yaml file.

        Returns:
            CompiledArtifacts object from real compilation.

        Raises:
            CompilationException: If any compilation stage fails.
        """
        return compile_pipeline(spec_path, manifest_path)

    return _compile_artifacts


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "requirement(id): Mark test as covering a specific requirement",
    )
