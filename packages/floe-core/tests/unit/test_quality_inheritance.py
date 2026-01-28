"""Unit tests for quality configuration inheritance resolver.

Tests the three-tier inheritance resolution (Enterprise → Domain → Product)
and locked setting enforcement (FLOE-DQ107).

T074: Three-tier inheritance resolution
T075: Locked setting enforcement
"""

from __future__ import annotations

import pytest

from floe_core.compilation.quality_inheritance import (
    merge_gate_tiers,
    resolve_quality_inheritance,
)
from floe_core.quality_errors import QualityOverrideError
from floe_core.schemas.quality_config import (
    GateTier,
    QualityConfig,
    QualityGates,
)


class TestResolveQualityInheritance:
    """Test resolve_quality_inheritance function (T074)."""

    @pytest.mark.requirement("005B-FR-016")
    def test_single_level_enterprise_only(self) -> None:
        """Test inheritance with only enterprise config."""
        enterprise = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                gold=GateTier(min_test_coverage=100),
            ),
        )
        result = resolve_quality_inheritance(enterprise, None, None)
        assert result.provider == "great_expectations"
        assert result.quality_gates.gold.min_test_coverage == 100

    @pytest.mark.requirement("005B-FR-016")
    def test_two_level_domain_overrides_enterprise(self) -> None:
        """Test domain overrides enterprise settings."""
        enterprise = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                silver=GateTier(min_test_coverage=70),
            ),
        )
        domain = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                silver=GateTier(min_test_coverage=80),
            ),
        )
        result = resolve_quality_inheritance(enterprise, domain, None)
        assert result.quality_gates.silver.min_test_coverage == 80

    @pytest.mark.requirement("005B-FR-016")
    def test_three_level_product_overrides_domain(self) -> None:
        """Test product overrides domain settings."""
        enterprise = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                bronze=GateTier(min_test_coverage=50),
            ),
        )
        domain = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                bronze=GateTier(min_test_coverage=60),
            ),
        )
        product = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                bronze=GateTier(min_test_coverage=70),
            ),
        )
        result = resolve_quality_inheritance(enterprise, domain, product)
        assert result.quality_gates.bronze.min_test_coverage == 70

    @pytest.mark.requirement("005B-FR-016")
    def test_inherits_unspecified_settings(self) -> None:
        """Test that unspecified settings are inherited from parent."""
        enterprise = QualityConfig(
            provider="great_expectations",
            check_timeout_seconds=600,
        )
        domain = QualityConfig(
            provider="great_expectations",
        )
        result = resolve_quality_inheritance(enterprise, domain, None)
        assert result.check_timeout_seconds == 300

    @pytest.mark.requirement("005B-FR-016")
    def test_empty_configs_returns_default(self) -> None:
        """Test that empty configs return default configuration."""
        result = resolve_quality_inheritance(None, None, None)
        assert result.provider == "great_expectations"

    @pytest.mark.requirement("005B-FR-016")
    def test_provider_from_last_level(self) -> None:
        """Test provider comes from the last specified level."""
        enterprise = QualityConfig(provider="great_expectations")
        product = QualityConfig(provider="dbt_expectations")
        result = resolve_quality_inheritance(enterprise, None, product)
        assert result.provider == "dbt_expectations"


class TestLockedSettingEnforcement:
    """Test locked setting (overridable: false) enforcement (T075)."""

    @pytest.mark.requirement("005B-FR-016b", "005B-FR-047")
    def test_locked_tier_prevents_override(self) -> None:
        """Test locked tier prevents lower level from overriding."""
        parent_gates = QualityGates(
            gold=GateTier(
                min_test_coverage=100,
                required_tests=["not_null", "unique"],
                overridable=False,
            ),
        )
        child_gates = QualityGates(
            gold=GateTier(
                min_test_coverage=80,
                required_tests=["not_null"],
            ),
        )
        with pytest.raises(QualityOverrideError) as exc_info:
            merge_gate_tiers(parent_gates, child_gates, "enterprise", "domain")
        assert exc_info.value.error_code == "FLOE-DQ107"
        assert exc_info.value.locked_by == "enterprise"
        assert exc_info.value.attempted_by == "domain"

    @pytest.mark.requirement("005B-FR-016b")
    def test_overridable_tier_allows_changes(self) -> None:
        """Test overridable tier allows lower level to change."""
        parent_gates = QualityGates(
            silver=GateTier(
                min_test_coverage=70,
                overridable=True,
            ),
        )
        child_gates = QualityGates(
            silver=GateTier(
                min_test_coverage=80,
            ),
        )
        result = merge_gate_tiers(parent_gates, child_gates, "enterprise", "domain")
        assert result.silver.min_test_coverage == 80

    @pytest.mark.requirement("005B-FR-016b")
    def test_same_value_not_considered_override(self) -> None:
        """Test same value is not considered an override attempt."""
        parent_gates = QualityGates(
            gold=GateTier(
                min_test_coverage=100,
                required_tests=["not_null", "unique"],
                overridable=False,
            ),
        )
        child_gates = QualityGates(
            gold=GateTier(
                min_test_coverage=100,
                required_tests=["not_null", "unique"],
            ),
        )
        result = merge_gate_tiers(parent_gates, child_gates, "enterprise", "domain")
        assert result.gold.min_test_coverage == 100

    @pytest.mark.requirement("005B-FR-016b", "005B-FR-047")
    def test_domain_locks_from_product(self) -> None:
        """Test domain can lock settings from product."""
        parent_gates = QualityGates(
            silver=GateTier(
                min_test_coverage=80,
                overridable=False,
            ),
        )
        child_gates = QualityGates(
            silver=GateTier(
                min_test_coverage=60,
            ),
        )
        with pytest.raises(QualityOverrideError) as exc_info:
            merge_gate_tiers(parent_gates, child_gates, "domain", "product")
        assert exc_info.value.locked_by == "domain"
        assert exc_info.value.attempted_by == "product"

    @pytest.mark.requirement("005B-FR-016b")
    def test_null_child_gates_inherits_parent(self) -> None:
        """Test None child gates inherits parent unchanged."""
        parent_gates = QualityGates(
            gold=GateTier(min_test_coverage=100),
        )
        result = merge_gate_tiers(parent_gates, None, "enterprise", "domain")
        assert result.gold.min_test_coverage == 100

    @pytest.mark.requirement("005B-FR-016b")
    def test_multiple_tiers_independent(self) -> None:
        """Test different tiers can have different lock status."""
        parent_gates = QualityGates(
            bronze=GateTier(min_test_coverage=50, overridable=True),
            silver=GateTier(min_test_coverage=80, overridable=False),
            gold=GateTier(min_test_coverage=100, overridable=True),
        )
        child_gates = QualityGates(
            bronze=GateTier(min_test_coverage=60),
            silver=GateTier(min_test_coverage=80),
            gold=GateTier(min_test_coverage=95),
        )
        result = merge_gate_tiers(parent_gates, child_gates, "enterprise", "domain")
        assert result.bronze.min_test_coverage == 60
        assert result.silver.min_test_coverage == 80
        assert result.gold.min_test_coverage == 95


class TestMergeGateTiersEdgeCases:
    """Edge case tests for merge_gate_tiers."""

    @pytest.mark.requirement("005B-FR-016b")
    def test_required_tests_change_detected(self) -> None:
        """Test changes to required_tests are detected."""
        parent_gates = QualityGates(
            gold=GateTier(
                min_test_coverage=100,
                required_tests=["not_null", "unique", "relationships"],
                overridable=False,
            ),
        )
        child_gates = QualityGates(
            gold=GateTier(
                min_test_coverage=100,
                required_tests=["not_null", "unique"],
            ),
        )
        with pytest.raises(QualityOverrideError):
            merge_gate_tiers(parent_gates, child_gates, "enterprise", "product")

    @pytest.mark.requirement("005B-FR-016b")
    def test_min_score_change_detected(self) -> None:
        """Test changes to min_score are detected."""
        parent_gates = QualityGates(
            silver=GateTier(
                min_test_coverage=80,
                min_score=90,
                overridable=False,
            ),
        )
        child_gates = QualityGates(
            silver=GateTier(
                min_test_coverage=80,
                min_score=70,
            ),
        )
        with pytest.raises(QualityOverrideError):
            merge_gate_tiers(parent_gates, child_gates, "enterprise", "domain")
