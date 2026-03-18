"""Unit tests for IcebergTableManagerConfig.from_governance() classmethod.

Tests AC-4 (from_governance builder) and AC-10 (duck typing, no circular import).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from floe_iceberg.models import IcebergTableManagerConfig

# ---------------------------------------------------------------------------
# Constants – single source of truth for expected defaults
# ---------------------------------------------------------------------------
EXPECTED_DEFAULT_TABLE_PROPERTIES: dict[str, str] = {
    "write.format.default": "parquet",
    "write.target-file-size-bytes": "134217728",
    "write.parquet.row-group-size-bytes": "134217728",
}

AGE_MS_KEY = "history.expire.max-snapshot-age-ms"
KEEP_KEY = "history.expire.min-snapshots-to-keep"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _governance(
    *,
    default_ttl_hours: int | None = None,
    snapshot_keep_last: int | None = None,
) -> SimpleNamespace:
    """Build a duck-typed governance object with only the specified fields."""
    attrs: dict[str, Any] = {}
    if default_ttl_hours is not None:
        attrs["default_ttl_hours"] = default_ttl_hours
    if snapshot_keep_last is not None:
        attrs["snapshot_keep_last"] = snapshot_keep_last
    return SimpleNamespace(**attrs)


# ===========================================================================
# AC-4: None governance returns default config
# ===========================================================================


class TestFromGovernanceNone:
    """Verify that passing None yields an unmodified default config."""

    @pytest.mark.requirement("AC-4")
    def test_none_returns_default_min_snapshots(self) -> None:
        """None governance must yield the model default min_snapshots_to_keep."""
        config = IcebergTableManagerConfig.from_governance(None)
        default = IcebergTableManagerConfig()
        assert config.min_snapshots_to_keep == default.min_snapshots_to_keep

    @pytest.mark.requirement("AC-4")
    def test_none_returns_default_table_properties(self) -> None:
        """None governance must preserve default table properties exactly."""
        config = IcebergTableManagerConfig.from_governance(None)
        assert config.default_table_properties == EXPECTED_DEFAULT_TABLE_PROPERTIES

    @pytest.mark.requirement("AC-4")
    def test_none_returns_default_retention_days(self) -> None:
        """None governance must not alter default_retention_days."""
        config = IcebergTableManagerConfig.from_governance(None)
        default = IcebergTableManagerConfig()
        assert config.default_retention_days == default.default_retention_days

    @pytest.mark.requirement("AC-4")
    def test_none_governance_has_no_age_ms_property(self) -> None:
        """None governance must NOT inject max-snapshot-age-ms."""
        config = IcebergTableManagerConfig.from_governance(None)
        assert AGE_MS_KEY not in config.default_table_properties

    @pytest.mark.requirement("AC-4")
    def test_none_governance_has_no_keep_property(self) -> None:
        """None governance must NOT inject min-snapshots-to-keep property."""
        config = IcebergTableManagerConfig.from_governance(None)
        assert KEEP_KEY not in config.default_table_properties


# ===========================================================================
# AC-4: Full governance mapping
# ===========================================================================


class TestFromGovernanceFull:
    """Verify full governance with both fields set."""

    @pytest.fixture()
    def config(self) -> IcebergTableManagerConfig:
        """Build config from governance(default_ttl_hours=24, snapshot_keep_last=3)."""
        gov = _governance(default_ttl_hours=24, snapshot_keep_last=3)
        return IcebergTableManagerConfig.from_governance(gov)

    # --- min_snapshots_to_keep field ---

    @pytest.mark.requirement("AC-4")
    def test_min_snapshots_mapped(self, config: IcebergTableManagerConfig) -> None:
        """snapshot_keep_last=3 must map to min_snapshots_to_keep=3."""
        assert config.min_snapshots_to_keep == 3

    # --- max-snapshot-age-ms property ---

    @pytest.mark.requirement("AC-4")
    def test_age_ms_exact_value(self, config: IcebergTableManagerConfig) -> None:
        """24 hours * 3600 * 1000 = 86400000, stored as string."""
        assert config.default_table_properties[AGE_MS_KEY] == "86400000"

    @pytest.mark.requirement("AC-4")
    def test_age_ms_is_string_type(self, config: IcebergTableManagerConfig) -> None:
        """Table property values must be strings."""
        assert isinstance(config.default_table_properties[AGE_MS_KEY], str)

    # --- min-snapshots-to-keep property ---

    @pytest.mark.requirement("AC-4")
    def test_keep_property_exact_value(self, config: IcebergTableManagerConfig) -> None:
        """snapshot_keep_last=3 stored as string '3' in table properties."""
        assert config.default_table_properties[KEEP_KEY] == "3"

    @pytest.mark.requirement("AC-4")
    def test_keep_property_is_string_type(self, config: IcebergTableManagerConfig) -> None:
        """Table property values must be strings."""
        assert isinstance(config.default_table_properties[KEEP_KEY], str)

    # --- Default properties preserved ---

    @pytest.mark.requirement("AC-4")
    def test_write_format_preserved(self, config: IcebergTableManagerConfig) -> None:
        """write.format.default must remain 'parquet' after governance merge."""
        assert config.default_table_properties["write.format.default"] == "parquet"

    @pytest.mark.requirement("AC-4")
    def test_target_file_size_preserved(self, config: IcebergTableManagerConfig) -> None:
        """write.target-file-size-bytes must remain 134217728 after merge."""
        assert config.default_table_properties["write.target-file-size-bytes"] == "134217728"

    @pytest.mark.requirement("AC-4")
    def test_row_group_size_preserved(self, config: IcebergTableManagerConfig) -> None:
        """write.parquet.row-group-size-bytes must remain 134217728."""
        assert config.default_table_properties["write.parquet.row-group-size-bytes"] == "134217728"

    @pytest.mark.requirement("AC-4")
    def test_total_property_count(self, config: IcebergTableManagerConfig) -> None:
        """Full governance adds exactly 2 new keys to the 3 defaults = 5 total."""
        assert len(config.default_table_properties) == 5


# ===========================================================================
# AC-4: Partial governance — only TTL set
# ===========================================================================


class TestFromGovernanceOnlyTTL:
    """Verify partial governance with only default_ttl_hours."""

    @pytest.fixture()
    def config(self) -> IcebergTableManagerConfig:
        """Build config from governance with only default_ttl_hours=48."""
        gov = _governance(default_ttl_hours=48)
        return IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_age_ms_from_48_hours(self, config: IcebergTableManagerConfig) -> None:
        """48 * 3600 * 1000 = 172800000."""
        assert config.default_table_properties[AGE_MS_KEY] == "172800000"

    @pytest.mark.requirement("AC-4")
    def test_min_snapshots_stays_default(self, config: IcebergTableManagerConfig) -> None:
        """Without snapshot_keep_last, min_snapshots_to_keep stays at default."""
        default = IcebergTableManagerConfig()
        assert config.min_snapshots_to_keep == default.min_snapshots_to_keep

    @pytest.mark.requirement("AC-4")
    def test_keep_property_absent(self, config: IcebergTableManagerConfig) -> None:
        """Without snapshot_keep_last, the keep property must NOT be injected."""
        assert KEEP_KEY not in config.default_table_properties

    @pytest.mark.requirement("AC-4")
    def test_write_format_preserved(self, config: IcebergTableManagerConfig) -> None:
        """Default properties must still be present."""
        assert config.default_table_properties["write.format.default"] == "parquet"


# ===========================================================================
# AC-4: Partial governance — only snapshot_keep_last set
# ===========================================================================


class TestFromGovernanceOnlySnapshot:
    """Verify partial governance with only snapshot_keep_last."""

    @pytest.fixture()
    def config(self) -> IcebergTableManagerConfig:
        """Build config from governance with only snapshot_keep_last=5."""
        gov = _governance(snapshot_keep_last=5)
        return IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_min_snapshots_mapped(self, config: IcebergTableManagerConfig) -> None:
        """snapshot_keep_last=5 must map to min_snapshots_to_keep=5."""
        assert config.min_snapshots_to_keep == 5

    @pytest.mark.requirement("AC-4")
    def test_keep_property_set(self, config: IcebergTableManagerConfig) -> None:
        """snapshot_keep_last=5 stored as '5' in table properties."""
        assert config.default_table_properties[KEEP_KEY] == "5"

    @pytest.mark.requirement("AC-4")
    def test_age_ms_absent(self, config: IcebergTableManagerConfig) -> None:
        """Without default_ttl_hours, the age-ms property must NOT be injected."""
        assert AGE_MS_KEY not in config.default_table_properties

    @pytest.mark.requirement("AC-4")
    def test_write_format_preserved(self, config: IcebergTableManagerConfig) -> None:
        """Default properties must still be present."""
        assert config.default_table_properties["write.format.default"] == "parquet"


# ===========================================================================
# AC-4: Conversion formula correctness across multiple values
# ===========================================================================


class TestTTLConversionFormula:
    """Verify hours * 3600 * 1000 formula for various inputs."""

    @pytest.mark.requirement("AC-4")
    @pytest.mark.parametrize(
        ("hours", "expected_ms"),
        [
            (1, "3600000"),
            (24, "86400000"),
            (168, "604800000"),  # 7 days
            (720, "2592000000"),  # 30 days
            (8760, "31536000000"),  # 365 days
        ],
        ids=["1h", "24h", "7d", "30d", "365d"],
    )
    def test_ttl_conversion(self, hours: int, expected_ms: str) -> None:
        """Verify exact millisecond conversion for various hour values."""
        gov = _governance(default_ttl_hours=hours)
        config = IcebergTableManagerConfig.from_governance(gov)
        assert config.default_table_properties[AGE_MS_KEY] == expected_ms


# ===========================================================================
# AC-10: Duck typing — no isinstance check on governance type
# ===========================================================================


class TestDuckTyping:
    """Verify from_governance() uses duck typing, not isinstance checks."""

    @pytest.mark.requirement("AC-10")
    def test_simple_namespace_accepted(self) -> None:
        """A SimpleNamespace with the right attrs must work (duck typing)."""
        gov = SimpleNamespace(default_ttl_hours=24, snapshot_keep_last=3)
        config = IcebergTableManagerConfig.from_governance(gov)
        assert config.min_snapshots_to_keep == 3
        assert config.default_table_properties[AGE_MS_KEY] == "86400000"

    @pytest.mark.requirement("AC-10")
    def test_dict_like_object_accepted(self) -> None:
        """A custom class with the right attributes must work."""

        class FakeGovernance:
            default_ttl_hours: int = 12
            snapshot_keep_last: int = 7

        config = IcebergTableManagerConfig.from_governance(FakeGovernance())
        assert config.min_snapshots_to_keep == 7
        assert config.default_table_properties[AGE_MS_KEY] == "43200000"
        assert config.default_table_properties[KEEP_KEY] == "7"

    @pytest.mark.requirement("AC-10")
    def test_no_runtime_import_of_resolved_governance(self) -> None:
        """from_governance must NOT import ResolvedGovernance at runtime.

        Importing floe_core at runtime would create a circular dependency.
        We verify using AST analysis to find any floe_core imports outside
        TYPE_CHECKING guards.
        """
        import ast
        import sys

        # Call the method to trigger any lazy imports
        gov = SimpleNamespace(default_ttl_hours=1, snapshot_keep_last=1)
        IcebergTableManagerConfig.from_governance(gov)

        # Parse the module source with AST for robust import detection
        iceberg_models = sys.modules["floe_iceberg.models"]
        module_source_file = iceberg_models.__file__
        assert module_source_file is not None
        with open(module_source_file) as f:
            tree = ast.parse(f.read())

        # Collect line numbers inside TYPE_CHECKING guards
        guarded_lines: set[int] = set()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Name)
                and node.test.id == "TYPE_CHECKING"
            ):
                for child in ast.walk(node):
                    if hasattr(child, "lineno"):
                        guarded_lines.add(child.lineno)

        # Check all top-level and nested imports for floe_core outside guards
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "floe_core" in node.module:
                assert node.lineno in guarded_lines, (
                    f"Runtime import of floe_core at line {node.lineno}: "
                    f"from {node.module} import ..."
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "floe_core" in alias.name:
                        assert node.lineno in guarded_lines, (
                            f"Runtime import of floe_core at line {node.lineno}: "
                            f"import {alias.name}"
                        )


# ===========================================================================
# AC-4: Return type is IcebergTableManagerConfig
# ===========================================================================


class TestReturnType:
    """Verify from_governance returns the correct type."""

    @pytest.mark.requirement("AC-4")
    def test_returns_iceberg_table_manager_config(self) -> None:
        """from_governance must return an IcebergTableManagerConfig instance."""
        config = IcebergTableManagerConfig.from_governance(None)
        assert isinstance(config, IcebergTableManagerConfig)

    @pytest.mark.requirement("AC-4")
    def test_returned_config_is_frozen(self) -> None:
        """Returned config must be frozen (immutable) like all IcebergTableManagerConfig."""
        gov = _governance(default_ttl_hours=24, snapshot_keep_last=3)
        config = IcebergTableManagerConfig.from_governance(gov)
        with pytest.raises(ValidationError):
            config.min_snapshots_to_keep = 99  # type: ignore[misc]


# ===========================================================================
# AC-4: Edge / boundary cases
# ===========================================================================


class TestEdgeCases:
    """Boundary and edge case tests for from_governance()."""

    @pytest.mark.requirement("AC-4")
    def test_snapshot_keep_last_one(self) -> None:
        """Minimum valid snapshot_keep_last=1."""
        gov = _governance(snapshot_keep_last=1)
        config = IcebergTableManagerConfig.from_governance(gov)
        assert config.min_snapshots_to_keep == 1
        assert config.default_table_properties[KEEP_KEY] == "1"

    @pytest.mark.requirement("AC-4")
    def test_max_valid_ttl_hours(self) -> None:
        """Maximum valid TTL (1 year) should compute correctly."""
        gov = _governance(default_ttl_hours=8760)  # 1 year = max
        config = IcebergTableManagerConfig.from_governance(gov)
        expected_ms = str(8760 * 3600 * 1000)
        assert config.default_table_properties[AGE_MS_KEY] == expected_ms

    @pytest.mark.requirement("AC-4")
    def test_governance_with_neither_field_behaves_like_none(self) -> None:
        """Governance object with no relevant fields should equal default config.

        This catches implementations that crash on missing attributes
        instead of treating them as absent.
        """
        gov = SimpleNamespace()  # No fields at all
        config = IcebergTableManagerConfig.from_governance(gov)
        default = IcebergTableManagerConfig()
        assert config.min_snapshots_to_keep == default.min_snapshots_to_keep
        assert config.default_table_properties == EXPECTED_DEFAULT_TABLE_PROPERTIES

    @pytest.mark.requirement("AC-4")
    def test_snapshot_keep_last_100(self) -> None:
        """Maximum valid snapshot_keep_last=100 (model max for min_snapshots_to_keep)."""
        gov = _governance(snapshot_keep_last=100)
        config = IcebergTableManagerConfig.from_governance(gov)
        assert config.min_snapshots_to_keep == 100
        assert config.default_table_properties[KEEP_KEY] == "100"

    @pytest.mark.requirement("AC-4")
    def test_ttl_one_hour(self) -> None:
        """Minimum practical TTL: 1 hour = 3600000 ms."""
        gov = _governance(default_ttl_hours=1)
        config = IcebergTableManagerConfig.from_governance(gov)
        assert config.default_table_properties[AGE_MS_KEY] == "3600000"

    @pytest.mark.requirement("AC-4")
    def test_different_governance_objects_produce_different_configs(self) -> None:
        """Two governance objects with different values must produce different configs.

        Catches hardcoded return values.
        """
        gov_a = _governance(default_ttl_hours=24, snapshot_keep_last=3)
        gov_b = _governance(default_ttl_hours=48, snapshot_keep_last=7)
        config_a = IcebergTableManagerConfig.from_governance(gov_a)
        config_b = IcebergTableManagerConfig.from_governance(gov_b)

        assert config_a.min_snapshots_to_keep != config_b.min_snapshots_to_keep
        assert (
            config_a.default_table_properties[AGE_MS_KEY]
            != config_b.default_table_properties[AGE_MS_KEY]
        )
        assert (
            config_a.default_table_properties[KEEP_KEY]
            != config_b.default_table_properties[KEEP_KEY]
        )


class TestFromGovernanceBoundsValidation:
    """Tests for defense-in-depth bounds checks in from_governance().

    Validates that out-of-range or wrong-type values raise ValueError
    even when bypassing Pydantic schema validation (duck-typed callers).
    """

    @pytest.mark.requirement("AC-4")
    def test_ttl_hours_exceeds_max_raises(self) -> None:
        """TTL above 8760 (1 year) must raise ValueError."""
        gov = _governance(default_ttl_hours=8761)
        with pytest.raises(ValueError, match="default_ttl_hours must be int in"):
            IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_ttl_hours_zero_raises(self) -> None:
        """TTL of 0 is below the minimum of 1."""
        gov = _governance(default_ttl_hours=0)
        with pytest.raises(ValueError, match="default_ttl_hours must be int in"):
            IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_ttl_hours_negative_raises(self) -> None:
        """Negative TTL must raise ValueError."""
        gov = _governance(default_ttl_hours=-1)
        with pytest.raises(ValueError, match="default_ttl_hours must be int in"):
            IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_snapshot_keep_last_exceeds_max_raises(self) -> None:
        """snapshot_keep_last above 100 must raise ValueError."""
        gov = _governance(snapshot_keep_last=101)
        with pytest.raises(ValueError, match="snapshot_keep_last must be int in"):
            IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_snapshot_keep_last_zero_raises(self) -> None:
        """snapshot_keep_last of 0 is below the minimum of 1."""
        gov = _governance(snapshot_keep_last=0)
        with pytest.raises(ValueError, match="snapshot_keep_last must be int in"):
            IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_snapshot_keep_last_negative_raises(self) -> None:
        """Negative snapshot_keep_last must raise ValueError."""
        gov = _governance(snapshot_keep_last=-5)
        with pytest.raises(ValueError, match="snapshot_keep_last must be int in"):
            IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_ttl_hours_non_int_raises(self) -> None:
        """Float TTL must raise ValueError (type check)."""
        gov = _governance(default_ttl_hours=24.5)
        with pytest.raises(ValueError, match="default_ttl_hours must be int in"):
            IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_snapshot_keep_last_non_int_raises(self) -> None:
        """String snapshot_keep_last must raise ValueError (type check)."""
        gov = _governance(snapshot_keep_last="5")
        with pytest.raises(ValueError, match="snapshot_keep_last must be int in"):
            IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_ttl_hours_bool_raises(self) -> None:
        """bool is a subclass of int but must be rejected."""
        gov = _governance(default_ttl_hours=True)
        with pytest.raises(ValueError, match="default_ttl_hours must be int in"):
            IcebergTableManagerConfig.from_governance(gov)

    @pytest.mark.requirement("AC-4")
    def test_snapshot_keep_last_bool_raises(self) -> None:
        """bool is a subclass of int but must be rejected."""
        gov = _governance(snapshot_keep_last=False)
        with pytest.raises(ValueError, match="snapshot_keep_last must be int in"):
            IcebergTableManagerConfig.from_governance(gov)
