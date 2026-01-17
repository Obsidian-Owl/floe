"""Unit tests for YAML loader module.

TDD tests for the compilation YAML loader. These tests define
the expected behavior before implementation.

Task: T025
Requirements: FR-001
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from floe_core.schemas.floe_spec import FloeSpec
    from floe_core.schemas.manifest import PlatformManifest


@pytest.fixture
def valid_floe_spec_yaml(tmp_path: Path) -> Path:
    """Create a valid floe.yaml file for testing."""
    yaml_content = """\
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-pipeline
  version: "1.0.0"
transforms:
  - name: stg_customers
  - name: fct_orders
    dependsOn:
      - stg_customers
"""
    spec_path = tmp_path / "floe.yaml"
    spec_path.write_text(yaml_content)
    return spec_path


@pytest.fixture
def valid_manifest_yaml(tmp_path: Path) -> Path:
    """Create a valid manifest.yaml file for testing."""
    yaml_content = """\
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: "1.0.0"
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
"""
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml_content)
    return manifest_path


@pytest.fixture
def invalid_yaml_file(tmp_path: Path) -> Path:
    """Create a file with invalid YAML syntax."""
    yaml_content = """\
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-pipeline
  version: "1.0.0"
transforms:
  - name: stg_customers
    invalid_indentation
"""
    spec_path = tmp_path / "invalid.yaml"
    spec_path.write_text(yaml_content)
    return spec_path


@pytest.fixture
def invalid_spec_yaml(tmp_path: Path) -> Path:
    """Create a YAML file that is valid YAML but invalid FloeSpec."""
    yaml_content = """\
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: INVALID_NAME_UPPERCASE
  version: "1.0.0"
transforms: []
"""
    spec_path = tmp_path / "invalid_spec.yaml"
    spec_path.write_text(yaml_content)
    return spec_path


class TestLoadFloeSpec:
    """Tests for load_floe_spec function."""

    @pytest.mark.requirement("2B-FR-001")
    def test_load_valid_floe_spec(self, valid_floe_spec_yaml: Path) -> None:
        """Test loading a valid floe.yaml file."""
        from floe_core.compilation.loader import load_floe_spec

        spec = load_floe_spec(valid_floe_spec_yaml)
        assert spec.metadata.name == "test-pipeline"
        assert spec.metadata.version == "1.0.0"
        assert len(spec.transforms) == 2
        assert spec.transforms[0].name == "stg_customers"

    @pytest.mark.requirement("2B-FR-001")
    def test_load_floe_spec_missing_file(self, tmp_path: Path) -> None:
        """Test loading a non-existent file raises CompilationException."""
        from floe_core.compilation.errors import CompilationException
        from floe_core.compilation.loader import load_floe_spec

        nonexistent = tmp_path / "nonexistent.yaml"
        with pytest.raises(CompilationException) as exc_info:
            load_floe_spec(nonexistent)
        assert exc_info.value.error.code == "E001"  # File not found
        assert exc_info.value.exit_code == 1  # Validation error

    @pytest.mark.requirement("2B-FR-001")
    def test_load_floe_spec_invalid_yaml(self, invalid_yaml_file: Path) -> None:
        """Test loading invalid YAML raises CompilationException."""
        from floe_core.compilation.errors import CompilationException
        from floe_core.compilation.loader import load_floe_spec

        with pytest.raises(CompilationException) as exc_info:
            load_floe_spec(invalid_yaml_file)
        assert exc_info.value.error.code == "E002"  # Invalid YAML syntax
        assert exc_info.value.exit_code == 1

    @pytest.mark.requirement("2B-FR-001")
    def test_load_floe_spec_validation_error(self, invalid_spec_yaml: Path) -> None:
        """Test loading valid YAML but invalid FloeSpec raises CompilationException."""
        from floe_core.compilation.errors import CompilationException
        from floe_core.compilation.loader import load_floe_spec

        with pytest.raises(CompilationException) as exc_info:
            load_floe_spec(invalid_spec_yaml)
        # Should be a validation error, not YAML parse error
        assert exc_info.value.exit_code == 1

    @pytest.mark.requirement("2B-FR-001")
    def test_load_floe_spec_returns_floe_spec_type(self, valid_floe_spec_yaml: Path) -> None:
        """Test that load_floe_spec returns a FloeSpec instance."""
        from floe_core.compilation.loader import load_floe_spec
        from floe_core.schemas.floe_spec import FloeSpec

        spec = load_floe_spec(valid_floe_spec_yaml)
        assert isinstance(spec, FloeSpec)


class TestLoadManifest:
    """Tests for load_manifest function."""

    @pytest.mark.requirement("2B-FR-001")
    def test_load_valid_manifest(self, valid_manifest_yaml: Path) -> None:
        """Test loading a valid manifest.yaml file."""
        from floe_core.compilation.loader import load_manifest

        manifest = load_manifest(valid_manifest_yaml)
        assert manifest.metadata.name == "test-platform"
        assert manifest.metadata.version == "1.0.0"
        assert manifest.plugins is not None

    @pytest.mark.requirement("2B-FR-001")
    def test_load_manifest_missing_file(self, tmp_path: Path) -> None:
        """Test loading a non-existent manifest raises CompilationException."""
        from floe_core.compilation.errors import CompilationException
        from floe_core.compilation.loader import load_manifest

        nonexistent = tmp_path / "nonexistent.yaml"
        with pytest.raises(CompilationException) as exc_info:
            load_manifest(nonexistent)
        assert exc_info.value.error.code == "E001"  # File not found
        assert exc_info.value.exit_code == 1

    @pytest.mark.requirement("2B-FR-001")
    def test_load_manifest_returns_manifest_type(self, valid_manifest_yaml: Path) -> None:
        """Test that load_manifest returns a PlatformManifest instance."""
        from floe_core.compilation.loader import load_manifest
        from floe_core.schemas.manifest import PlatformManifest

        manifest = load_manifest(valid_manifest_yaml)
        assert isinstance(manifest, PlatformManifest)
