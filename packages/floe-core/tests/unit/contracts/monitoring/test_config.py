"""Unit tests for contract monitoring configuration models.

Tests: T016 (Epic 3D)
Requirements: 3D-FR-001, 3D-FR-002, 3D-FR-007
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from floe_core.contracts.monitoring.config import (
    AlertChannelRoutingRule,
    AlertConfig,
    CheckIntervalConfig,
    MonitoringConfig,
    RegisteredContract,
    SeverityThresholds,
)
from floe_core.contracts.monitoring.violations import ViolationSeverity

# --- CheckIntervalConfig Tests ---


@pytest.mark.requirement("3D-FR-001")
def test_check_interval_config_defaults() -> None:
    """Test CheckIntervalConfig default values match FR-003 specification."""
    config = CheckIntervalConfig()

    assert config.freshness_minutes == 15
    assert config.schema_drift_minutes == 60
    assert config.quality_minutes == 360
    assert config.availability_minutes == 5


@pytest.mark.requirement("3D-FR-001")
def test_check_interval_config_custom_values() -> None:
    """Test CheckIntervalConfig accepts custom values."""
    config = CheckIntervalConfig(
        freshness_minutes=10,
        schema_drift_minutes=30,
        quality_minutes=180,
        availability_minutes=2,
    )

    assert config.freshness_minutes == 10
    assert config.schema_drift_minutes == 30
    assert config.quality_minutes == 180
    assert config.availability_minutes == 2


@pytest.mark.requirement("3D-FR-001")
def test_check_interval_config_frozen() -> None:
    """Test CheckIntervalConfig is frozen (immutable)."""
    config = CheckIntervalConfig()

    with pytest.raises(ValidationError, match="frozen"):
        config.freshness_minutes = 99


@pytest.mark.requirement("3D-FR-001")
def test_check_interval_config_extra_forbid() -> None:
    """Test CheckIntervalConfig rejects unknown fields."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CheckIntervalConfig(unknown_field="value")  # type: ignore[call-arg]


@pytest.mark.requirement("3D-FR-001")
def test_check_interval_config_validation_ge_1() -> None:
    """Test CheckIntervalConfig rejects values < 1."""
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        CheckIntervalConfig(freshness_minutes=0)

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        CheckIntervalConfig(schema_drift_minutes=-5)


# --- SeverityThresholds Tests ---


@pytest.mark.requirement("3D-FR-007")
def test_severity_thresholds_defaults() -> None:
    """Test SeverityThresholds default values."""
    config = SeverityThresholds()

    assert config.info_pct == pytest.approx(80.0)
    assert config.warning_pct == pytest.approx(90.0)
    assert config.critical_count == 3
    assert config.critical_window_hours == 24


@pytest.mark.requirement("3D-FR-007")
def test_severity_thresholds_custom_values() -> None:
    """Test SeverityThresholds accepts custom values."""
    config = SeverityThresholds(
        info_pct=70.0,
        warning_pct=85.0,
        critical_count=5,
        critical_window_hours=12,
    )

    assert config.info_pct == pytest.approx(70.0)
    assert config.warning_pct == pytest.approx(85.0)
    assert config.critical_count == 5
    assert config.critical_window_hours == 12


@pytest.mark.requirement("3D-FR-007")
def test_severity_thresholds_frozen() -> None:
    """Test SeverityThresholds is frozen (immutable)."""
    config = SeverityThresholds()

    with pytest.raises(ValidationError, match="frozen"):
        config.info_pct = 99.0


@pytest.mark.requirement("3D-FR-007")
def test_severity_thresholds_pct_validation() -> None:
    """Test SeverityThresholds validates percentage ranges (0-100)."""
    # Test upper bound violation
    with pytest.raises(ValidationError, match="less than or equal to 100"):
        SeverityThresholds(info_pct=101.0)

    # Test lower bound violation
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        SeverityThresholds(warning_pct=-5.0)

    # Test boundary values are accepted
    config = SeverityThresholds(info_pct=0.0, warning_pct=100.0)
    assert config.info_pct == pytest.approx(0.0)
    assert config.warning_pct == pytest.approx(100.0)


@pytest.mark.requirement("3D-FR-007")
def test_severity_thresholds_count_hours_validation() -> None:
    """Test SeverityThresholds validates critical_count and critical_window_hours >= 1."""
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        SeverityThresholds(critical_count=0)

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        SeverityThresholds(critical_window_hours=-1)


# --- AlertChannelRoutingRule Tests ---


@pytest.mark.requirement("3D-FR-007")
def test_alert_channel_routing_rule_valid() -> None:
    """Test AlertChannelRoutingRule accepts valid construction."""
    rule = AlertChannelRoutingRule(
        channel_name="slack",
        min_severity=ViolationSeverity.WARNING,
    )

    assert rule.channel_name == "slack"
    assert rule.min_severity == ViolationSeverity.WARNING
    assert rule.contract_filter is None


@pytest.mark.requirement("3D-FR-007")
def test_alert_channel_routing_rule_with_filter() -> None:
    """Test AlertChannelRoutingRule accepts optional contract_filter."""
    rule = AlertChannelRoutingRule(
        channel_name="email",
        min_severity=ViolationSeverity.ERROR,
        contract_filter="orders_*",
    )

    assert rule.channel_name == "email"
    assert rule.min_severity == ViolationSeverity.ERROR
    assert rule.contract_filter == "orders_*"


@pytest.mark.requirement("3D-FR-007")
def test_alert_channel_routing_rule_frozen() -> None:
    """Test AlertChannelRoutingRule is frozen (immutable)."""
    rule = AlertChannelRoutingRule(
        channel_name="slack",
        min_severity=ViolationSeverity.INFO,
    )

    with pytest.raises(ValidationError, match="frozen"):
        rule.channel_name = "email"


@pytest.mark.requirement("3D-FR-007")
def test_alert_channel_routing_rule_severity_enum() -> None:
    """Test AlertChannelRoutingRule accepts all ViolationSeverity enum values."""
    for severity in ViolationSeverity:
        rule = AlertChannelRoutingRule(
            channel_name="test_channel",
            min_severity=severity,
        )
        assert rule.min_severity == severity


# --- AlertConfig Tests ---


@pytest.mark.requirement("3D-FR-007")
def test_alert_config_defaults() -> None:
    """Test AlertConfig default values."""
    config = AlertConfig()

    assert config.routing_rules == []
    assert config.dedup_window_minutes == 30
    assert config.rate_limit_per_contract == 10
    assert config.rate_limit_window_minutes == 60


@pytest.mark.requirement("3D-FR-007")
def test_alert_config_custom_values() -> None:
    """Test AlertConfig accepts custom values."""
    rules = [
        AlertChannelRoutingRule(
            channel_name="slack",
            min_severity=ViolationSeverity.WARNING,
        ),
    ]
    config = AlertConfig(
        routing_rules=rules,
        dedup_window_minutes=15,
        rate_limit_per_contract=5,
        rate_limit_window_minutes=120,
    )

    assert len(config.routing_rules) == 1
    assert config.routing_rules[0].channel_name == "slack"
    assert config.dedup_window_minutes == 15
    assert config.rate_limit_per_contract == 5
    assert config.rate_limit_window_minutes == 120


@pytest.mark.requirement("3D-FR-007")
def test_alert_config_frozen() -> None:
    """Test AlertConfig is frozen (immutable)."""
    config = AlertConfig()

    with pytest.raises(ValidationError, match="frozen"):
        config.dedup_window_minutes = 99


@pytest.mark.requirement("3D-FR-007")
def test_alert_config_extra_forbid() -> None:
    """Test AlertConfig rejects unknown fields."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AlertConfig(unknown_field="value")  # type: ignore[call-arg]


# --- MonitoringConfig Tests ---


@pytest.mark.requirement("3D-FR-001")
def test_monitoring_config_defaults() -> None:
    """Test MonitoringConfig default values."""
    config = MonitoringConfig()

    assert config.enabled is True
    assert config.mode == "scheduled"
    assert config.retention_days == 90
    assert config.clock_skew_tolerance_seconds == 60
    assert config.check_timeout_seconds == 30


@pytest.mark.requirement("3D-FR-001")
def test_monitoring_config_nested_defaults() -> None:
    """Test MonitoringConfig nested models have correct defaults."""
    config = MonitoringConfig()

    # Check CheckIntervalConfig defaults
    assert config.check_intervals.freshness_minutes == 15
    assert config.check_intervals.schema_drift_minutes == 60
    assert config.check_intervals.quality_minutes == 360
    assert config.check_intervals.availability_minutes == 5

    # Check SeverityThresholds defaults
    assert config.severity_thresholds.info_pct == pytest.approx(80.0)
    assert config.severity_thresholds.warning_pct == pytest.approx(90.0)
    assert config.severity_thresholds.critical_count == 3
    assert config.severity_thresholds.critical_window_hours == 24

    # Check AlertConfig defaults
    assert config.alerts.routing_rules == []
    assert config.alerts.dedup_window_minutes == 30
    assert config.alerts.rate_limit_per_contract == 10
    assert config.alerts.rate_limit_window_minutes == 60


@pytest.mark.requirement("3D-FR-001")
def test_monitoring_config_mode_validation() -> None:
    """Test MonitoringConfig mode accepts valid values and rejects invalid."""
    # Valid modes
    for mode in ["scheduled", "continuous", "on_demand"]:
        config = MonitoringConfig(mode=mode)
        assert config.mode == mode

    # Invalid mode
    with pytest.raises(ValidationError, match="String should match pattern"):
        MonitoringConfig(mode="invalid")


@pytest.mark.requirement("3D-FR-001")
def test_monitoring_config_frozen() -> None:
    """Test MonitoringConfig is frozen (immutable)."""
    config = MonitoringConfig()

    with pytest.raises(ValidationError, match="frozen"):
        config.enabled = False


@pytest.mark.requirement("3D-FR-001")
def test_monitoring_config_extra_forbid() -> None:
    """Test MonitoringConfig rejects unknown fields."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MonitoringConfig(unknown_field="value")  # type: ignore[call-arg]


@pytest.mark.requirement("3D-FR-001")
def test_monitoring_config_custom_nested() -> None:
    """Test MonitoringConfig accepts custom nested configurations."""
    custom_intervals = CheckIntervalConfig(
        freshness_minutes=10,
        schema_drift_minutes=30,
    )
    custom_thresholds = SeverityThresholds(
        info_pct=75.0,
        warning_pct=85.0,
    )
    custom_alerts = AlertConfig(
        dedup_window_minutes=15,
    )

    config = MonitoringConfig(
        enabled=False,
        mode="continuous",
        check_intervals=custom_intervals,
        severity_thresholds=custom_thresholds,
        alerts=custom_alerts,
        retention_days=30,
    )

    assert config.enabled is False
    assert config.mode == "continuous"
    assert config.check_intervals.freshness_minutes == 10
    assert config.severity_thresholds.info_pct == pytest.approx(75.0)
    assert config.alerts.dedup_window_minutes == 15
    assert config.retention_days == 30


# --- RegisteredContract Tests ---


@pytest.mark.requirement("3D-FR-002")
def test_registered_contract_valid() -> None:
    """Test RegisteredContract accepts valid construction."""
    now = datetime.now(tz=timezone.utc)
    contract = RegisteredContract(
        contract_name="orders_v1",
        contract_version="1.0.0",
        contract_data={"apiVersion": "v3.1.0"},
        connection_config={"catalog": "polaris"},
        registered_at=now,
    )

    assert contract.contract_name == "orders_v1"
    assert contract.contract_version == "1.0.0"
    assert contract.contract_data == {"apiVersion": "v3.1.0"}
    assert contract.connection_config == {"catalog": "polaris"}
    assert contract.registered_at == now
    assert contract.monitoring_overrides is None
    assert contract.last_check_times == {}
    assert contract.active is True


@pytest.mark.requirement("3D-FR-002")
def test_registered_contract_mutable() -> None:
    """Test RegisteredContract is NOT frozen (mutable runtime state)."""
    now = datetime.now(tz=timezone.utc)
    contract = RegisteredContract(
        contract_name="orders_v1",
        contract_version="1.0.0",
        contract_data={"apiVersion": "v3.1.0"},
        connection_config={"catalog": "polaris"},
        registered_at=now,
    )

    # Should allow mutation (unlike other monitoring models)
    contract.active = False
    assert contract.active is False

    contract.last_check_times["freshness"] = now
    assert "freshness" in contract.last_check_times


@pytest.mark.requirement("3D-FR-002")
def test_registered_contract_with_overrides() -> None:
    """Test RegisteredContract accepts monitoring_overrides."""
    now = datetime.now(tz=timezone.utc)
    overrides = MonitoringConfig(
        enabled=False,
        mode="on_demand",
    )
    contract = RegisteredContract(
        contract_name="orders_v1",
        contract_version="1.0.0",
        contract_data={"apiVersion": "v3.1.0"},
        connection_config={"catalog": "polaris"},
        registered_at=now,
        monitoring_overrides=overrides,
    )

    assert contract.monitoring_overrides is not None
    assert contract.monitoring_overrides.enabled is False
    assert contract.monitoring_overrides.mode == "on_demand"


@pytest.mark.requirement("3D-FR-002")
def test_registered_contract_extra_forbid() -> None:
    """Test RegisteredContract rejects unknown fields."""
    now = datetime.now(tz=timezone.utc)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RegisteredContract(
            contract_name="orders_v1",
            contract_version="1.0.0",
            contract_data={"apiVersion": "v3.1.0"},
            connection_config={"catalog": "polaris"},
            registered_at=now,
            unknown_field="value",  # type: ignore[call-arg]
        )


@pytest.mark.requirement("3D-FR-002")
def test_registered_contract_defaults() -> None:
    """Test RegisteredContract default values."""
    now = datetime.now(tz=timezone.utc)
    contract = RegisteredContract(
        contract_name="orders_v1",
        contract_version="1.0.0",
        contract_data={"apiVersion": "v3.1.0"},
        connection_config={"catalog": "polaris"},
        registered_at=now,
    )

    # Verify defaults are set correctly
    assert contract.monitoring_overrides is None
    assert contract.last_check_times == {}
    assert contract.active is True


@pytest.mark.requirement("3D-FR-002")
def test_registered_contract_last_check_times_mutability() -> None:
    """Test RegisteredContract last_check_times can be updated."""
    now = datetime.now(tz=timezone.utc)
    contract = RegisteredContract(
        contract_name="orders_v1",
        contract_version="1.0.0",
        contract_data={"apiVersion": "v3.1.0"},
        connection_config={"catalog": "polaris"},
        registered_at=now,
    )

    # Mutate last_check_times
    check_time = datetime.now(tz=timezone.utc)
    contract.last_check_times["freshness"] = check_time
    contract.last_check_times["schema_drift"] = check_time

    assert len(contract.last_check_times) == 2
    assert contract.last_check_times["freshness"] == check_time
    assert contract.last_check_times["schema_drift"] == check_time
