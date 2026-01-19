"""Contract tests for GovernanceConfig schema stability.

These tests ensure the GovernanceConfig schema remains stable and
backward-compatible after Epic 3A extensions. Breaking changes
should fail these tests.

Task: T010
Requirements: FR-013, FR-017, US2 (Policy Configuration via Manifest)

Contract Guarantees:
1. Existing GovernanceConfig fields remain unchanged
2. New fields (naming, quality_gates) are optional (default None)
3. JSON Schema output matches contracts/governance-schema.json
4. Existing manifests continue to work (backward compatibility)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Path to contract schema
CONTRACTS_DIR = Path(__file__).parent.parent.parent / "specs" / "3a-policy-enforcer" / "contracts"


class TestGovernanceConfigContract:
    """Contract tests for GovernanceConfig schema stability.

    These tests verify that the GovernanceConfig schema structure
    remains stable and backward-compatible.
    """

    @pytest.mark.requirement("3A-US2-FR013")
    def test_existing_fields_unchanged(self) -> None:
        """Contract: Existing GovernanceConfig fields remain unchanged.

        Original fields from before Epic 3A:
        - pii_encryption: Literal["required", "optional"] | None
        - audit_logging: Literal["enabled", "disabled"] | None
        - policy_enforcement_level: Literal["off", "warn", "strict"] | None
        - data_retention_days: int | None
        """
        from floe_core.schemas.manifest import GovernanceConfig

        # Original fields MUST still work as before
        config = GovernanceConfig(
            pii_encryption="required",
            audit_logging="enabled",
            policy_enforcement_level="strict",
            data_retention_days=90,
        )
        assert config.pii_encryption == "required"
        assert config.audit_logging == "enabled"
        assert config.policy_enforcement_level == "strict"
        assert config.data_retention_days == 90

    @pytest.mark.requirement("3A-US2-FR013")
    def test_new_fields_optional(self) -> None:
        """Contract: New fields (naming, quality_gates) default to None.

        Backward compatibility requirement: existing code that doesn't
        use the new fields should continue to work.
        """
        from floe_core.schemas.manifest import GovernanceConfig

        # Config without new fields MUST work
        config = GovernanceConfig(pii_encryption="required")
        assert config.naming is None
        assert config.quality_gates is None

    @pytest.mark.requirement("3A-US2-FR013")
    def test_new_fields_present_in_schema(self) -> None:
        """Contract: New fields are present in JSON Schema.

        The JSON Schema MUST include definitions for:
        - naming: NamingConfig
        - quality_gates: QualityGatesConfig
        """
        from floe_core.schemas.manifest import GovernanceConfig

        schema = GovernanceConfig.model_json_schema()
        properties = schema.get("properties", {})

        # New fields MUST be in schema
        assert "naming" in properties, "naming field missing from schema"
        assert "quality_gates" in properties, "quality_gates field missing from schema"

    @pytest.mark.requirement("3A-US2-FR013")
    def test_json_schema_matches_contract(self) -> None:
        """Contract: JSON Schema matches contracts/governance-schema.json.

        The generated Pydantic schema MUST match the contract specification.
        This ensures the contract document stays in sync with implementation.
        """
        from floe_core.schemas.manifest import GovernanceConfig

        contract_path = CONTRACTS_DIR / "governance-schema.json"
        if not contract_path.exists():
            pytest.skip(f"Contract file not found: {contract_path}")

        with open(contract_path) as f:
            contract_schema = json.load(f)

        generated_schema = GovernanceConfig.model_json_schema()

        # Property names MUST match
        contract_props = set(contract_schema.get("properties", {}).keys())
        generated_props = set(generated_schema.get("properties", {}).keys())

        assert contract_props == generated_props, (
            f"Schema property mismatch.\n"
            f"In contract but not generated: {contract_props - generated_props}\n"
            f"In generated but not contract: {generated_props - contract_props}"
        )

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_contract(self) -> None:
        """Contract: NamingConfig has stable structure.

        NamingConfig MUST have:
        - enforcement: Literal["off", "warn", "strict"] (default: "warn")
        - pattern: Literal["medallion", "kimball", "custom"] (default: "medallion")
        - custom_patterns: list[str] | None (default: None)
        """
        from floe_core.schemas.governance import NamingConfig

        # Defaults MUST match contract
        config = NamingConfig()
        assert config.enforcement == "warn"
        assert config.pattern == "medallion"
        assert config.custom_patterns is None

        # All enum values MUST be accepted
        for enforcement in ["off", "warn", "strict"]:
            NamingConfig(enforcement=enforcement)

        for pattern in ["medallion", "kimball", "custom"]:
            if pattern == "custom":
                NamingConfig(pattern=pattern, custom_patterns=["^test_.*$"])
            else:
                NamingConfig(pattern=pattern)

    @pytest.mark.requirement("3A-US2-FR013")
    def test_quality_gates_config_contract(self) -> None:
        """Contract: QualityGatesConfig has stable structure.

        QualityGatesConfig MUST have:
        - minimum_test_coverage: int (0-100, default: 80)
        - require_descriptions: bool (default: False)
        - require_column_descriptions: bool (default: False)
        - block_on_failure: bool (default: True)
        - layer_thresholds: LayerThresholds | None (default: None)
        - zero_column_coverage_behavior: Literal[...] (default: "report_na")
        """
        from floe_core.schemas.governance import QualityGatesConfig

        # Defaults MUST match contract
        config = QualityGatesConfig()
        assert config.minimum_test_coverage == 80
        assert config.require_descriptions is False
        assert config.require_column_descriptions is False
        assert config.block_on_failure is True
        assert config.layer_thresholds is None
        assert config.zero_column_coverage_behavior == "report_na"

    @pytest.mark.requirement("3A-US2-FR013")
    def test_layer_thresholds_contract(self) -> None:
        """Contract: LayerThresholds has stable structure.

        LayerThresholds MUST have:
        - bronze: int (0-100, default: 50)
        - silver: int (0-100, default: 80)
        - gold: int (0-100, default: 100)
        """
        from floe_core.schemas.governance import LayerThresholds

        # Defaults MUST match contract
        thresholds = LayerThresholds()
        assert thresholds.bronze == 50
        assert thresholds.silver == 80
        assert thresholds.gold == 100

    @pytest.mark.requirement("3A-US2-FR013")
    def test_governance_config_frozen(self) -> None:
        """Contract: GovernanceConfig is immutable (frozen=True).

        This is a security requirement - governance settings should not
        be mutable after creation.
        """
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig(pii_encryption="required")

        # Model MUST be frozen
        assert config.model_config.get("frozen", False) is True

    @pytest.mark.requirement("3A-US2-FR013")
    def test_governance_config_forbids_extra(self) -> None:
        """Contract: GovernanceConfig rejects unknown fields (extra=forbid).

        This prevents typos from silently being ignored.
        """
        from floe_core.schemas.manifest import GovernanceConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GovernanceConfig(unknown_field="value")  # type: ignore[call-arg]


class TestGovernanceConfigInheritanceContract:
    """Contract tests for GovernanceConfig inheritance validation.

    These tests verify that the inheritance strengthening rules
    remain stable.
    """

    @pytest.mark.requirement("3A-US2-FR017")
    def test_existing_inheritance_rules_unchanged(self) -> None:
        """Contract: Existing inheritance rules remain unchanged.

        Original strength ordering:
        - pii_encryption: required > optional
        - audit_logging: enabled > disabled
        - policy_enforcement_level: strict > warn > off
        - data_retention_days: higher is stricter
        """
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import (
            SecurityPolicyViolationError,
            validate_security_policy_not_weakened,
        )

        # Existing rules MUST still work
        parent = GovernanceConfig(pii_encryption="required")
        child = GovernanceConfig(pii_encryption="optional")

        with pytest.raises(SecurityPolicyViolationError):
            validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_new_inheritance_rules_added(self) -> None:
        """Contract: New inheritance rules for naming and quality_gates.

        New strength ordering:
        - naming.enforcement: strict > warn > off
        - quality_gates.minimum_test_coverage: higher is stricter
        - quality_gates.require_descriptions: True > False
        """
        from floe_core.schemas.governance import NamingConfig, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import (
            SecurityPolicyViolationError,
            validate_security_policy_not_weakened,
        )

        # Naming enforcement weakening MUST be rejected
        parent = GovernanceConfig(naming=NamingConfig(enforcement="strict"))
        child = GovernanceConfig(naming=NamingConfig(enforcement="warn"))

        with pytest.raises(SecurityPolicyViolationError):
            validate_security_policy_not_weakened(parent, child)

        # Coverage reduction MUST be rejected
        parent = GovernanceConfig(
            quality_gates=QualityGatesConfig(minimum_test_coverage=80)
        )
        child = GovernanceConfig(
            quality_gates=QualityGatesConfig(minimum_test_coverage=60)
        )

        with pytest.raises(SecurityPolicyViolationError):
            validate_security_policy_not_weakened(parent, child)
