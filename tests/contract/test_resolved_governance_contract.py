"""Contract tests for ResolvedGovernance lifecycle fields and drift detection.

These tests validate contract stability for the governance lifecycle fields
(default_ttl_hours, snapshot_keep_last) added in T1, plus drift detection
to ensure GovernanceConfig scalar fields stay synchronized with ResolvedGovernance.

Task: T5
Acceptance Criteria:
    - AC-6: COMPILED_ARTIFACTS_VERSION is "0.10.0"
    - AC-7: Old JSON without lifecycle fields deserializes correctly
    - AC-9: ResolvedGovernance has all lifecycle fields; drift detection

Contract Guarantees:
1. COMPILED_ARTIFACTS_VERSION == "0.10.0" (contract-level assertion)
2. CompiledArtifacts JSON without default_ttl_hours/snapshot_keep_last -> both None
3. ResolvedGovernance contains every scalar field from GovernanceConfig
4. Adding a new scalar field to GovernanceConfig without mirroring in
   ResolvedGovernance causes test failure (drift detection)
"""

from __future__ import annotations

import json
import types
from datetime import datetime
from typing import Any, Union, get_args, get_origin

import pytest
from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    ObservabilityConfig,
    ProductIdentity,
    ResolvedGovernance,
)
from floe_core.schemas.manifest import GovernanceConfig
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION
from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Known scalar fields in GovernanceConfig that MUST appear in ResolvedGovernance
# ---------------------------------------------------------------------------
EXPECTED_SCALAR_FIELDS: frozenset[str] = frozenset(
    {
        "pii_encryption",
        "audit_logging",
        "policy_enforcement_level",
        "data_retention_days",
        "default_ttl_hours",
        "snapshot_keep_last",
        "stale_table_recovery_mode",
    }
)
"""The concrete scalar governance fields today.

If you add a scalar field to GovernanceConfig, add it here AND to
ResolvedGovernance -- the drift detection test will catch omissions
from either side.
"""

# ---------------------------------------------------------------------------
# Complex (BaseModel / list-of-BaseModel) fields we expect to EXCLUDE
# ---------------------------------------------------------------------------
EXPECTED_COMPLEX_FIELDS: frozenset[str] = frozenset(
    {
        "naming",
        "quality_gates",
        "custom_rules",
        "policy_overrides",
        "data_contracts",
        "rbac",
        "secret_scanning",
        "network_policies",
        "policies",
    }
)
"""Complex GovernanceConfig fields (BaseModel subclasses or lists thereof).

These are NOT expected in ResolvedGovernance -- only scalar fields are.
"""


def _is_scalar_field(annotation: Any) -> bool:
    """Determine whether a Pydantic field annotation is scalar (not a BaseModel subclass).

    A field is scalar if none of the concrete types in its annotation are
    BaseModel subclasses or lists/sequences of BaseModel subclasses.

    Args:
        annotation: The type annotation from model_fields[name].annotation.

    Returns:
        True if the field is a simple scalar type (int, str, Literal, etc.).
    """
    # Unwrap Optional / Union
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        inner_types = get_args(annotation)
        # Filter out NoneType
        concrete = [t for t in inner_types if t is not type(None)]
        return all(_is_scalar_field(t) for t in concrete)

    # Annotated[X, ...] -- unwrap to the first arg
    from typing import Annotated

    if get_origin(annotation) is Annotated:
        inner_args = get_args(annotation)
        if inner_args:
            return _is_scalar_field(inner_args[0])

    # list[X] -- check element type
    if origin is list:
        element_args = get_args(annotation)
        if element_args:
            return _is_scalar_field(element_args[0])
        return True  # bare list is scalar-ish

    # Check if origin is a BaseModel subclass (e.g., for generic aliases)
    if origin is not None and isinstance(origin, type):
        try:
            if issubclass(origin, BaseModel):
                return False
        except TypeError:
            pass

    # Direct class check
    if isinstance(annotation, type):
        try:
            if issubclass(annotation, BaseModel):
                return False
        except TypeError:
            pass

    return True


def _extract_scalar_field_names(model_cls: type[BaseModel]) -> set[str]:
    """Extract field names from a Pydantic model that have scalar annotations.

    Args:
        model_cls: A Pydantic BaseModel subclass.

    Returns:
        Set of field names whose annotations are scalar (not BaseModel subclasses).
    """
    scalar_names: set[str] = set()
    for name, field_info in model_cls.model_fields.items():
        if _is_scalar_field(field_info.annotation):
            scalar_names.add(name)
    return scalar_names


def _make_observability() -> ObservabilityConfig:
    """Build a minimal valid ObservabilityConfig for test fixtures.

    Returns:
        A valid ObservabilityConfig instance.
    """
    return ObservabilityConfig(
        telemetry=TelemetryConfig(
            enabled=True,
            resource_attributes=ResourceAttributes(
                service_name="test",
                service_version="1.0.0",
                deployment_environment="dev",
                floe_namespace="test",
                floe_product_name="test",
                floe_product_version="1.0.0",
                floe_mode="dev",
            ),
        ),
        lineage_namespace="test-namespace",
    )


def _make_minimal_artifacts_dict() -> dict[str, Any]:
    """Build a minimal CompiledArtifacts dictionary for JSON deserialization tests.

    Returns governance=None (omitted) to simulate old-format JSON.

    Returns:
        Dictionary that can be passed to CompiledArtifacts.model_validate().
    """
    artifacts = CompiledArtifacts(
        version=COMPILED_ARTIFACTS_VERSION,
        metadata=CompilationMetadata(
            compiled_at=datetime.now(),
            floe_version="0.1.0",
            source_hash="sha256:abc123",
            product_name="test-product",
            product_version="1.0.0",
        ),
        identity=ProductIdentity(
            product_id="default.test_product",
            domain="default",
            repository="github.com/acme/test",
        ),
        mode="simple",
        inheritance_chain=[],
        observability=_make_observability(),
    )
    return json.loads(artifacts.model_dump_json())


# ===========================================================================
# AC-6: COMPILED_ARTIFACTS_VERSION contract
# ===========================================================================


class TestCompiledArtifactsVersionContract:
    """Contract: COMPILED_ARTIFACTS_VERSION must be exactly 0.10.0."""

    @pytest.mark.requirement("T5-AC-6")
    def test_compiled_artifacts_version_is_0_10_0(self) -> None:
        """AC-6: COMPILED_ARTIFACTS_VERSION MUST be '0.10.0'.

        This is a contract-level assertion that locks the version constant.
        If the version changes, this test must be updated deliberately --
        never silently.
        """
        assert COMPILED_ARTIFACTS_VERSION == "0.10.0", (
            f"COMPILED_ARTIFACTS_VERSION is {COMPILED_ARTIFACTS_VERSION!r}, "
            "expected '0.10.0'. If this is intentional, update this contract test."
        )

    @pytest.mark.requirement("T5-AC-6")
    def test_default_version_on_new_artifacts_is_0_10_0(self) -> None:
        """AC-6: A new CompiledArtifacts instance defaults to version '0.10.0'.

        Ensures the constant is actually wired into the schema default,
        not just defined but unused.
        """
        artifacts = CompiledArtifacts(
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version="0.1.0",
                source_hash="sha256:abc",
                product_name="test",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.test",
                domain="default",
                repository="github.com/acme/test",
            ),
            inheritance_chain=[],
            observability=_make_observability(),
        )
        assert artifacts.version == "0.10.0"


# ===========================================================================
# AC-7: Backward compatibility -- old JSON without lifecycle fields
# ===========================================================================


class TestBackwardCompatibility:
    """Contract: Old CompiledArtifacts JSON deserializes with lifecycle fields as None."""

    @pytest.mark.requirement("T5-AC-7")
    def test_old_json_without_default_ttl_hours_deserializes(self) -> None:
        """AC-7: JSON missing default_ttl_hours yields governance.default_ttl_hours == None.

        Simulates an artifact produced before the lifecycle fields were added.
        The governance block exists but lacks the new fields.
        """
        data = _make_minimal_artifacts_dict()
        # Add a governance block WITHOUT the lifecycle fields
        data["governance"] = {
            "pii_encryption": "required",
            "audit_logging": "enabled",
            "policy_enforcement_level": "strict",
            "data_retention_days": 90,
            # NOTE: no default_ttl_hours, no snapshot_keep_last
        }

        artifacts = CompiledArtifacts.model_validate(data)

        assert artifacts.governance is not None
        assert artifacts.governance.default_ttl_hours is None
        assert artifacts.governance.snapshot_keep_last is None
        # Existing fields still correct
        assert artifacts.governance.pii_encryption == "required"
        assert artifacts.governance.audit_logging == "enabled"
        assert artifacts.governance.policy_enforcement_level == "strict"
        assert artifacts.governance.data_retention_days == 90

    @pytest.mark.requirement("T5-AC-7")
    def test_old_json_without_governance_block_deserializes(self) -> None:
        """AC-7: JSON with no governance block at all yields governance == None.

        Even older artifacts may not have a governance block at all.
        """
        data = _make_minimal_artifacts_dict()
        # Ensure no governance key
        data.pop("governance", None)

        artifacts = CompiledArtifacts.model_validate(data)

        assert artifacts.governance is None

    @pytest.mark.requirement("T5-AC-7")
    def test_old_json_with_empty_governance_deserializes(self) -> None:
        """AC-7: JSON with empty governance object yields all fields as None.

        An intermediate case: governance key exists but all fields are default.
        """
        data = _make_minimal_artifacts_dict()
        data["governance"] = {}

        artifacts = CompiledArtifacts.model_validate(data)

        assert artifacts.governance is not None
        assert artifacts.governance.default_ttl_hours is None
        assert artifacts.governance.snapshot_keep_last is None
        assert artifacts.governance.pii_encryption is None
        assert artifacts.governance.audit_logging is None
        assert artifacts.governance.policy_enforcement_level is None
        assert artifacts.governance.data_retention_days is None

    @pytest.mark.requirement("T5-AC-7")
    def test_json_round_trip_with_lifecycle_fields_set(self, tmp_path: Any) -> None:
        """AC-7: Lifecycle fields survive JSON serialization round-trip.

        Ensures the new fields are not silently dropped during serialization.
        """
        from pathlib import Path

        artifacts = CompiledArtifacts(
            version=COMPILED_ARTIFACTS_VERSION,
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version="0.1.0",
                source_hash="sha256:round_trip",
                product_name="roundtrip-product",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.roundtrip",
                domain="default",
                repository="github.com/acme/test",
            ),
            mode="simple",
            inheritance_chain=[],
            observability=_make_observability(),
            governance=ResolvedGovernance(
                pii_encryption="required",
                audit_logging="enabled",
                default_ttl_hours=720,
                snapshot_keep_last=10,
            ),
        )

        out = Path(tmp_path) / "artifacts.json"
        artifacts.to_json_file(out)
        loaded = CompiledArtifacts.from_json_file(out)

        assert loaded.governance is not None
        assert loaded.governance.default_ttl_hours == 720
        assert loaded.governance.snapshot_keep_last == 10
        assert loaded.governance.pii_encryption == "required"
        assert loaded.governance.audit_logging == "enabled"


# ===========================================================================
# AC-9: ResolvedGovernance contains lifecycle fields
# ===========================================================================


class TestResolvedGovernanceLifecycleFields:
    """Contract: ResolvedGovernance exposes the lifecycle scalar fields."""

    @pytest.mark.requirement("T5-AC-9")
    def test_resolved_governance_has_default_ttl_hours(self) -> None:
        """AC-9: ResolvedGovernance has default_ttl_hours field that accepts int | None."""
        gov = ResolvedGovernance(default_ttl_hours=24)
        assert gov.default_ttl_hours == 24

        gov_none = ResolvedGovernance()
        assert gov_none.default_ttl_hours is None

    @pytest.mark.requirement("T5-AC-9")
    def test_resolved_governance_has_snapshot_keep_last(self) -> None:
        """AC-9: ResolvedGovernance has snapshot_keep_last field that accepts int | None."""
        gov = ResolvedGovernance(snapshot_keep_last=5)
        assert gov.snapshot_keep_last == 5

        gov_none = ResolvedGovernance()
        assert gov_none.snapshot_keep_last is None

    @pytest.mark.requirement("T5-AC-9")
    def test_resolved_governance_default_ttl_hours_validates_range(self) -> None:
        """AC-9: default_ttl_hours enforces ge=1, le=8760 constraints."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="default_ttl_hours"):
            ResolvedGovernance(default_ttl_hours=0)

        with pytest.raises(ValidationError, match="default_ttl_hours"):
            ResolvedGovernance(default_ttl_hours=-1)

        with pytest.raises(ValidationError, match="default_ttl_hours"):
            ResolvedGovernance(default_ttl_hours=8761)

        # Boundary values -- must succeed
        gov_min = ResolvedGovernance(default_ttl_hours=1)
        assert gov_min.default_ttl_hours == 1

        gov_max = ResolvedGovernance(default_ttl_hours=8760)
        assert gov_max.default_ttl_hours == 8760

    @pytest.mark.requirement("T5-AC-9")
    def test_resolved_governance_snapshot_keep_last_validates_range(self) -> None:
        """AC-9: snapshot_keep_last enforces ge=1, le=100 constraints."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="snapshot_keep_last"):
            ResolvedGovernance(snapshot_keep_last=0)

        with pytest.raises(ValidationError, match="snapshot_keep_last"):
            ResolvedGovernance(snapshot_keep_last=-1)

        with pytest.raises(ValidationError, match="snapshot_keep_last"):
            ResolvedGovernance(snapshot_keep_last=101)

        # Boundary values -- must succeed
        gov_min = ResolvedGovernance(snapshot_keep_last=1)
        assert gov_min.snapshot_keep_last == 1

        gov_max = ResolvedGovernance(snapshot_keep_last=100)
        assert gov_max.snapshot_keep_last == 100

    @pytest.mark.requirement("T5-AC-9")
    def test_resolved_governance_all_scalar_fields_present(self) -> None:
        """AC-9: ResolvedGovernance has ALL known scalar governance fields.

        Explicitly enumerates every scalar field and verifies it can be
        set and read back. A hardcoded return value would fail here because
        we check each field's actual value, not just its existence.
        """
        gov = ResolvedGovernance(
            pii_encryption="required",
            audit_logging="enabled",
            policy_enforcement_level="strict",
            data_retention_days=365,
            default_ttl_hours=720,
            snapshot_keep_last=10,
        )
        assert gov.pii_encryption == "required"
        assert gov.audit_logging == "enabled"
        assert gov.policy_enforcement_level == "strict"
        assert gov.data_retention_days == 365
        assert gov.default_ttl_hours == 720
        assert gov.snapshot_keep_last == 10

    @pytest.mark.requirement("T5-AC-9")
    def test_resolved_governance_field_names_match_governance_config(self) -> None:
        """AC-9: Every scalar field name in GovernanceConfig exists in ResolvedGovernance.

        This ensures field naming is consistent between the manifest-side
        GovernanceConfig and the compiled-artifacts-side ResolvedGovernance.
        """
        resolved_field_names = set(ResolvedGovernance.model_fields.keys())

        for field_name in EXPECTED_SCALAR_FIELDS:
            assert field_name in GovernanceConfig.model_fields, (
                f"Expected scalar field {field_name!r} missing from GovernanceConfig. "
                "Update EXPECTED_SCALAR_FIELDS if this field was removed."
            )
            assert field_name in resolved_field_names, (
                f"Scalar field {field_name!r} exists in GovernanceConfig but is "
                f"missing from ResolvedGovernance. Fields in ResolvedGovernance: "
                f"{sorted(resolved_field_names)}"
            )


# ===========================================================================
# AC-9: Drift detection -- programmatic scalar field extraction
# ===========================================================================


class TestGovernanceFieldDriftDetection:
    """Contract: Programmatic drift detection between GovernanceConfig and ResolvedGovernance.

    These tests use introspection to extract scalar fields from GovernanceConfig
    and assert they all exist in ResolvedGovernance. If a developer adds a new
    scalar field to GovernanceConfig but forgets to add it to ResolvedGovernance,
    these tests will catch the omission.
    """

    @pytest.mark.requirement("T5-AC-9")
    def test_scalar_field_extraction_correctness(self) -> None:
        """Verify the _is_scalar_field helper correctly classifies known fields.

        This meta-test ensures the drift detection machinery itself is correct
        before we rely on it for the actual drift test.
        """
        governance_fields = GovernanceConfig.model_fields

        # Known scalars MUST be detected as scalar
        for name in EXPECTED_SCALAR_FIELDS:
            annotation = governance_fields[name].annotation
            assert _is_scalar_field(annotation), (
                f"Field {name!r} with annotation {annotation!r} was NOT detected "
                "as scalar, but it should be."
            )

        # Known complex fields MUST NOT be detected as scalar
        for name in EXPECTED_COMPLEX_FIELDS:
            if name not in governance_fields:
                continue  # skip if field not present in this version
            annotation = governance_fields[name].annotation
            assert not _is_scalar_field(annotation), (
                f"Field {name!r} with annotation {annotation!r} was detected "
                "as scalar, but it is a complex field (BaseModel subclass)."
            )

    @pytest.mark.requirement("T5-AC-9")
    def test_all_governance_scalar_fields_in_resolved_governance(self) -> None:
        """AC-9 drift detection: every GovernanceConfig scalar in ResolvedGovernance.

        This is the core drift-detection test. It programmatically extracts
        scalar fields from GovernanceConfig and asserts each one exists in
        ResolvedGovernance. If someone adds a new scalar field to
        GovernanceConfig without mirroring it, this test fails.
        """
        governance_scalars = _extract_scalar_field_names(GovernanceConfig)
        resolved_field_names = set(ResolvedGovernance.model_fields.keys())

        missing = governance_scalars - resolved_field_names
        assert missing == set(), (
            f"GovernanceConfig has scalar fields {sorted(missing)} that are "
            f"NOT present in ResolvedGovernance. Either add them to "
            f"ResolvedGovernance or, if they are intentionally excluded, "
            f"reclassify them as complex fields.\n"
            f"GovernanceConfig scalars: {sorted(governance_scalars)}\n"
            f"ResolvedGovernance fields: {sorted(resolved_field_names)}"
        )

    @pytest.mark.requirement("T5-AC-9")
    def test_expected_scalar_fields_matches_programmatic_extraction(self) -> None:
        """AC-9: The hardcoded EXPECTED_SCALAR_FIELDS matches programmatic extraction.

        This catches drift in the TEST ITSELF: if a new scalar field is added
        to GovernanceConfig but EXPECTED_SCALAR_FIELDS is not updated, this
        test will fail, forcing the developer to update both the test constant
        AND ResolvedGovernance.
        """
        governance_scalars = _extract_scalar_field_names(GovernanceConfig)

        assert governance_scalars == EXPECTED_SCALAR_FIELDS, (
            f"Programmatically extracted scalar fields {sorted(governance_scalars)} "
            f"do not match EXPECTED_SCALAR_FIELDS {sorted(EXPECTED_SCALAR_FIELDS)}. "
            "If a new scalar field was added to GovernanceConfig, update "
            "EXPECTED_SCALAR_FIELDS in this test file AND add the field to "
            "ResolvedGovernance."
        )

    @pytest.mark.requirement("T5-AC-9")
    def test_resolved_governance_has_no_extra_scalar_fields(self) -> None:
        """AC-9: ResolvedGovernance does not have scalar fields absent from GovernanceConfig.

        Bidirectional check: ensures ResolvedGovernance doesn't accumulate
        orphan fields that no longer exist in GovernanceConfig.
        """
        governance_scalars = _extract_scalar_field_names(GovernanceConfig)
        resolved_fields = set(ResolvedGovernance.model_fields.keys())

        # ResolvedGovernance fields should be a subset of GovernanceConfig scalars
        extra = resolved_fields - governance_scalars
        assert extra == set(), (
            f"ResolvedGovernance has fields {sorted(extra)} that are NOT "
            f"scalar fields in GovernanceConfig. Either these fields are "
            f"orphaned (remove them) or GovernanceConfig is missing them."
        )

    @pytest.mark.requirement("T5-AC-9")
    def test_governance_config_field_count_guard(self) -> None:
        """AC-9: Guard against undetected GovernanceConfig field additions.

        Locks the total field count of GovernanceConfig so any new field
        addition (scalar OR complex) triggers a test update. This is a
        safety net beyond the scalar extraction logic.
        """
        total_fields = len(GovernanceConfig.model_fields)
        expected_total = len(EXPECTED_SCALAR_FIELDS) + len(EXPECTED_COMPLEX_FIELDS)

        assert total_fields == expected_total, (
            f"GovernanceConfig has {total_fields} fields but we expected "
            f"{expected_total} ({len(EXPECTED_SCALAR_FIELDS)} scalar + "
            f"{len(EXPECTED_COMPLEX_FIELDS)} complex). A field was added or "
            "removed without updating this contract test. Update "
            "EXPECTED_SCALAR_FIELDS or EXPECTED_COMPLEX_FIELDS accordingly."
        )
