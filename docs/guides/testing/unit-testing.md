# Unit Testing

Unit tests are fast, isolated tests that run on CI runners without Kubernetes infrastructure.

---

## Test Structure

```
tests/
├── unit/
│   ├── floe_core/
│   │   ├── test_compiler.py
│   │   ├── test_schemas.py
│   │   └── test_validation.py
│   ├── floe_cli/
│   │   ├── test_commands.py
│   │   └── test_init.py
│   ├── floe_dagster/
│   │   ├── test_asset_factory.py
│   │   └── test_lineage.py
│   └── floe_dbt/
│       ├── test_profiles.py
│       └── test_executor.py
├── integration/
│   └── ...
└── e2e/
    └── ...
```

---

## Unit Test Examples

### Schema Validation Tests

```python
# tests/unit/floe_core/test_schemas.py
import pytest
from pydantic import ValidationError
from floe_core.schemas import FloeSpec, ComputeConfig, ComputeTarget

class TestFloeSpec:
    """Tests for FloeSpec schema."""

    def test_valid_spec(self):
        """Valid spec should parse successfully."""
        spec = FloeSpec(
            name="test-pipeline",
            version="1.0",
            compute=ComputeConfig(target=ComputeTarget.DUCKDB),
        )
        assert spec.name == "test-pipeline"
        assert spec.compute.target == ComputeTarget.DUCKDB

    def test_missing_name_fails(self):
        """Missing name should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            FloeSpec(
                version="1.0",
                compute=ComputeConfig(target=ComputeTarget.DUCKDB),
            )
        assert "name" in str(exc_info.value)

    def test_invalid_target_fails(self):
        """Invalid compute target should raise ValidationError."""
        with pytest.raises(ValidationError):
            FloeSpec(
                name="test",
                compute=ComputeConfig(target="invalid"),
            )

    @pytest.mark.parametrize("target", list(ComputeTarget))
    def test_all_targets_valid(self, target: ComputeTarget):
        """All defined targets should be valid."""
        spec = FloeSpec(
            name="test",
            compute=ComputeConfig(target=target),
        )
        assert spec.compute.target == target
```

### Profile Generation Tests

```python
# tests/unit/floe_dbt/test_profiles.py
import pytest
from floe_core.schemas import CompiledArtifacts, ComputeConfig, ComputeTarget
from floe_dbt.profiles import generate_profiles

class TestProfileGeneration:
    """Tests for dbt profile generation."""

    def test_duckdb_profile(self):
        """DuckDB profile should be generated correctly."""
        artifacts = create_artifacts(
            target=ComputeTarget.DUCKDB,
            properties={"path": "/tmp/test.duckdb"},
        )

        profiles = generate_profiles(artifacts)

        assert profiles["floe"]["outputs"]["default"]["type"] == "duckdb"
        assert profiles["floe"]["outputs"]["default"]["path"] == "/tmp/test.duckdb"

    def test_snowflake_profile_uses_env_vars(self):
        """Snowflake profile should use environment variable references."""
        artifacts = create_artifacts(target=ComputeTarget.SNOWFLAKE)

        profiles = generate_profiles(artifacts)

        output = profiles["floe"]["outputs"]["default"]
        assert "{{ env_var('SNOWFLAKE_ACCOUNT') }}" in output["account"]
        assert "{{ env_var('SNOWFLAKE_PASSWORD') }}" in output["password"]

def create_artifacts(**kwargs) -> CompiledArtifacts:
    """Helper to create test artifacts."""
    return CompiledArtifacts(
        metadata={"compiled_at": "2024-01-01", "floe_core_version": "0.1.0", "source_hash": "abc"},
        compute=ComputeConfig(**kwargs),
        transforms=[],
        observability={},
    )
```

---

## Property-Based Testing

Use Hypothesis for property-based testing to discover edge cases:

```python
# tests/unit/floe_core/test_compiler_properties.py
from hypothesis import given, strategies as st
from floe_core.compiler import Compiler
from floe_core.schemas import FloeSpec

class TestCompilerProperties:
    """Property-based tests for compiler."""

    @given(
        name=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        version=st.sampled_from(["1.0", "1.1", "2.0"]),
    )
    def test_compile_produces_valid_artifacts(self, name: str, version: str):
        """Compiling any valid spec should produce valid artifacts."""
        spec = FloeSpec(
            name=name.strip(),
            version=version,
            compute={"target": "duckdb"},
        )

        compiler = Compiler()
        artifacts = compiler.compile_spec(spec)

        # Artifacts should always contain the original spec values
        assert artifacts.compute.target.value == "duckdb"

    @given(st.binary())
    def test_invalid_yaml_raises_error(self, data: bytes):
        """Invalid YAML should raise ConfigurationError."""
        from floe_core.errors import ConfigurationError

        compiler = Compiler()
        try:
            compiler.compile_bytes(data)
            # If no error, data happened to be valid YAML + valid spec
        except ConfigurationError:
            pass  # Expected
        except Exception as e:
            pytest.fail(f"Unexpected exception type: {type(e)}")
```

---

## Running Unit Tests

```bash
# Run all unit tests
uv run pytest tests/unit -v

# Run with coverage
uv run pytest tests/unit -v --cov=floe_core --cov=floe_cli --cov-report=xml

# Run specific test file
uv run pytest tests/unit/floe_core/test_schemas.py -v

# Run tests matching pattern
uv run pytest tests/unit -k "test_valid" -v
```

---

## Related

- [Testing Index](index.md)
- [Integration Testing](integration-testing.md)
- [Code Quality](code-quality.md)
