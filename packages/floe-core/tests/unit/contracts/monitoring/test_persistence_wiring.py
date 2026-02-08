"""Unit tests for persistence wiring in ContractMonitor.

Tasks: T059, T060 (Epic 3D)
Requirements: FR-031, FR-032
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.monitor import ContractMonitor
from floe_core.contracts.monitoring.violations import (
    CheckStatus,
    ViolationType,
)


class MockRepository:
    """Mock repository for testing persistence wiring."""

    def __init__(self) -> None:
        """Initialize mock repository with empty storage."""
        self.check_results: list[dict[str, Any]] = []
        self.violations: list[dict[str, Any]] = []
        self.registered: list[dict[str, Any]] = []
        self.daily_aggregates: list[dict[str, Any]] = []

    async def save_check_result(self, result: dict[str, Any]) -> uuid.UUID:
        """Save a check result.

        Args:
            result: Check result data to save.

        Returns:
            UUID of saved check result.
        """
        self.check_results.append(result)
        return uuid.uuid4()

    async def save_violation(self, violation: dict[str, Any]) -> uuid.UUID:
        """Save a violation.

        Args:
            violation: Violation data to save.

        Returns:
            UUID of saved violation.
        """
        self.violations.append(violation)
        return uuid.uuid4()

    async def get_registered_contracts(
        self, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """Get registered contracts from repository.

        Args:
            active_only: If True, return only active contracts.

        Returns:
            List of contract data dictionaries.
        """
        if active_only:
            return [c for c in self.registered if c.get("active", True)]
        return list(self.registered)

    async def cleanup_expired(self, retention_days: int = 90) -> int:
        """Delete raw check results and violations older than retention period.

        Daily aggregates are NEVER deleted (indefinite retention).

        Args:
            retention_days: Number of days to retain raw data.

        Returns:
            Total number of deleted records.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=retention_days)
        deleted_count: int = 0

        # Delete old check results
        results_to_delete = [
            r
            for r in self.check_results
            if r.get("timestamp") and r["timestamp"] < cutoff
        ]
        deleted_count += len(results_to_delete)
        for r in results_to_delete:
            self.check_results.remove(r)

        # Delete old violations
        violations_to_delete = [
            v for v in self.violations if v.get("timestamp") and v["timestamp"] < cutoff
        ]
        deleted_count += len(violations_to_delete)
        for v in violations_to_delete:
            self.violations.remove(v)

        return deleted_count


@pytest.fixture
def mock_repository() -> MockRepository:
    """Create a mock repository for tests.

    Returns:
        MockRepository instance.
    """
    return MockRepository()


@pytest.fixture
def config() -> MonitoringConfig:
    """Create test monitoring config.

    Returns:
        MonitoringConfig instance.
    """
    return MonitoringConfig()


@pytest.fixture
def sample_contract() -> RegisteredContract:
    """Create a sample registered contract.

    Returns:
        RegisteredContract instance with complete data for testing.
    """
    now = datetime.now(tz=timezone.utc)
    return RegisteredContract(
        contract_name="orders_v1",
        contract_version="1.0.0",
        contract_data={
            "schema": {"name": "string", "total": "decimal"},
            "sla": {
                "freshness": {
                    "threshold_minutes": 60,
                }
            },
            "dataset": {
                "last_updated": now.isoformat(),
            },
        },
        connection_config={
            "catalog": "polaris",
            "namespace": "prod",
        },
        registered_at=now,
    )


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-031")
async def test_run_check_persists_pass_result(
    config: MonitoringConfig,
    sample_contract: RegisteredContract,
    mock_repository: MockRepository,
) -> None:
    """Test that PASS result is saved to repository.

    Verifies that when a check passes, the result is persisted to the
    repository with correct status and details.
    """
    monitor = ContractMonitor(
        config=config,
        repository=mock_repository,
    )
    monitor.register_contract(sample_contract)

    # Mock the freshness check to return PASS
    result = await monitor.run_check("orders_v1", ViolationType.FRESHNESS)

    # Verify result was persisted
    assert len(mock_repository.check_results) == 1
    saved = mock_repository.check_results[0]
    assert saved["contract_name"] == "orders_v1"
    assert saved["check_type"] == ViolationType.FRESHNESS.value
    assert saved["status"] == result.status.value
    assert "duration_seconds" in saved


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-031")
async def test_run_check_persists_quality_result(
    config: MonitoringConfig,
    sample_contract: RegisteredContract,
    mock_repository: MockRepository,
) -> None:
    """Test that quality check result is saved to repository.

    Verifies that when a quality check runs with an AsyncMock plugin,
    the result is persisted. Quality checks with mock plugins produce
    no violation (SKIP/ERROR status).
    """
    # Create a monitor with mocked quality plugin
    mock_quality_plugin = AsyncMock()
    monitor = ContractMonitor(
        config=config,
        quality_plugin=mock_quality_plugin,
        repository=mock_repository,
    )
    monitor.register_contract(sample_contract)

    # Run quality check (will call quality_plugin)
    result = await monitor.run_check("orders_v1", ViolationType.QUALITY)

    # Verify result was persisted
    assert len(mock_repository.check_results) == 1
    saved_result = mock_repository.check_results[0]
    assert saved_result["contract_name"] == "orders_v1"
    assert saved_result["check_type"] == ViolationType.QUALITY.value

    # Quality check with AsyncMock plugin produces no violation (SKIP/ERROR status)
    assert result.violation is None
    assert len(mock_repository.violations) == 0


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-031")
async def test_run_check_no_repository(
    config: MonitoringConfig,
    sample_contract: RegisteredContract,
) -> None:
    """Test that monitor works without repository.

    Verifies that when no repository is configured, checks still execute
    successfully and no errors occur.
    """
    monitor = ContractMonitor(config=config)
    monitor.register_contract(sample_contract)

    # Should not raise error
    result = await monitor.run_check("orders_v1", ViolationType.FRESHNESS)
    assert result.status == CheckStatus.PASS


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-031")
async def test_persist_error_does_not_propagate(
    config: MonitoringConfig,
    sample_contract: RegisteredContract,
) -> None:
    """Test that repository errors do not propagate from run_check.

    Verifies that if persistence fails, the check still returns a result
    and the error is logged but not raised.
    """
    # Create a mock repository that raises on save
    failing_repository = AsyncMock()
    failing_repository.save_check_result = AsyncMock(
        side_effect=RuntimeError("DB error")
    )

    monitor = ContractMonitor(
        config=config,
        repository=failing_repository,
    )
    monitor.register_contract(sample_contract)

    # Should not raise error despite repository failure
    result = await monitor.run_check("orders_v1", ViolationType.FRESHNESS)
    assert result.status == CheckStatus.PASS


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-032")
async def test_discover_contracts_from_db(
    config: MonitoringConfig,
    mock_repository: MockRepository,
) -> None:
    """Test contract discovery loads from database.

    Verifies that discover_contracts loads active contracts from the
    repository and registers them in the monitor.
    """
    # Populate repository with registered contracts
    mock_repository.registered = [
        {
            "contract_name": "orders_v1",
            "contract_version": "1.0.0",
            "contract_data": {"schema": {"id": "int"}},
            "connection_config": {"catalog": "polaris"},
            "monitoring_overrides": None,
            "registered_at": datetime.now(tz=timezone.utc),
            "last_check_times": {},
            "active": True,
        },
        {
            "contract_name": "customers_v1",
            "contract_version": "1.0.0",
            "contract_data": {"schema": {"name": "string"}},
            "connection_config": {"catalog": "polaris"},
            "monitoring_overrides": None,
            "registered_at": datetime.now(tz=timezone.utc),
            "last_check_times": {},
            "active": True,
        },
    ]

    monitor = ContractMonitor(config=config, repository=mock_repository)

    # Discover contracts
    discovered = await monitor.discover_contracts()

    assert discovered == 2
    assert "orders_v1" in monitor.registered_contracts
    assert "customers_v1" in monitor.registered_contracts


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-032")
async def test_discover_contracts_empty_db(
    config: MonitoringConfig,
    mock_repository: MockRepository,
) -> None:
    """Test contract discovery with empty database.

    Verifies that discover_contracts returns 0 when the database has no
    registered contracts.
    """
    monitor = ContractMonitor(config=config, repository=mock_repository)

    discovered = await monitor.discover_contracts()

    assert discovered == 0
    assert len(monitor.registered_contracts) == 0


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-032")
async def test_discover_contracts_no_repository(
    config: MonitoringConfig,
) -> None:
    """Test contract discovery without repository.

    Verifies that discover_contracts returns 0 when no repository is
    configured and logs appropriate warning.
    """
    monitor = ContractMonitor(config=config)

    discovered = await monitor.discover_contracts()

    assert discovered == 0
    assert len(monitor.registered_contracts) == 0


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-032")
async def test_discover_contracts_db_error(
    config: MonitoringConfig,
) -> None:
    """Test contract discovery handles database errors gracefully.

    Verifies that if the repository raises an error during discovery,
    the error is logged and discover_contracts returns 0.
    """
    # Create a mock repository that raises on get_registered_contracts
    failing_repository = AsyncMock()
    failing_repository.get_registered_contracts = AsyncMock(
        side_effect=RuntimeError("DB connection failed")
    )

    monitor = ContractMonitor(config=config, repository=failing_repository)

    # Should not raise error
    discovered = await monitor.discover_contracts()

    assert discovered == 0
    assert len(monitor.registered_contracts) == 0


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-032")
async def test_discover_contracts_filters_inactive(
    config: MonitoringConfig,
    mock_repository: MockRepository,
) -> None:
    """Test that discovery only loads active contracts.

    Verifies that inactive contracts in the database are not loaded
    during discovery.
    """
    # Populate repository with active and inactive contracts
    mock_repository.registered = [
        {
            "contract_name": "active_v1",
            "contract_version": "1.0.0",
            "contract_data": {"schema": {"id": "int"}},
            "connection_config": {"catalog": "polaris"},
            "monitoring_overrides": None,
            "registered_at": datetime.now(tz=timezone.utc),
            "last_check_times": {},
            "active": True,
        },
        {
            "contract_name": "inactive_v1",
            "contract_version": "1.0.0",
            "contract_data": {"schema": {"id": "int"}},
            "connection_config": {"catalog": "polaris"},
            "monitoring_overrides": None,
            "registered_at": datetime.now(tz=timezone.utc),
            "last_check_times": {},
            "active": False,
        },
    ]

    monitor = ContractMonitor(config=config, repository=mock_repository)

    discovered = await monitor.discover_contracts()

    # Only active contract should be discovered
    assert discovered == 1
    assert "active_v1" in monitor.registered_contracts
    assert "inactive_v1" not in monitor.registered_contracts


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-032")
async def test_discover_contracts_skips_already_registered(
    config: MonitoringConfig,
    mock_repository: MockRepository,
    sample_contract: RegisteredContract,
) -> None:
    """Test that discovery skips contracts already registered.

    Verifies that if a contract is already registered in the monitor,
    discovery does not overwrite it.
    """
    # Manually register a contract
    monitor = ContractMonitor(config=config, repository=mock_repository)
    monitor.register_contract(sample_contract)

    # Add same contract to repository
    mock_repository.registered = [
        {
            "contract_name": "orders_v1",  # Same as sample_contract
            "contract_version": "2.0.0",  # Different version
            "contract_data": {"schema": {"id": "int"}},
            "connection_config": {"catalog": "polaris"},
            "monitoring_overrides": None,
            "registered_at": datetime.now(tz=timezone.utc),
            "last_check_times": {},
            "active": True,
        },
    ]

    discovered = await monitor.discover_contracts()

    # Should not discover the already-registered contract
    assert discovered == 0
    # Original contract should remain
    assert monitor.registered_contracts["orders_v1"].contract_version == "1.0.0"


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-034")
async def test_cleanup_expired_deletes_old_check_results(
    config: MonitoringConfig,
    mock_repository: MockRepository,
) -> None:
    """Test cleanup_expired deletes raw check results older than retention period.

    Verifies that check results older than 90 days (default) are deleted,
    while recent ones are preserved.
    """
    now = datetime.now(tz=timezone.utc)
    old_timestamp = now - timedelta(days=91)  # Older than 90 days
    recent_timestamp = now - timedelta(days=30)  # Within 90 days

    # Add old and recent check results
    mock_repository.check_results = [
        {
            "id": uuid.uuid4(),
            "contract_name": "orders_v1",
            "check_type": "freshness",
            "status": "pass",
            "duration_seconds": 1.5,
            "timestamp": old_timestamp,
            "details": {},
        },
        {
            "id": uuid.uuid4(),
            "contract_name": "orders_v1",
            "check_type": "freshness",
            "status": "pass",
            "duration_seconds": 1.5,
            "timestamp": recent_timestamp,
            "details": {},
        },
    ]

    # Run cleanup through ContractMonitor
    monitor = ContractMonitor(config=config, repository=mock_repository)
    deleted_count = await monitor.cleanup_expired(retention_days=90)

    # Verify old result was deleted, recent one preserved
    assert deleted_count == 1
    assert len(mock_repository.check_results) == 1
    assert mock_repository.check_results[0]["timestamp"] == recent_timestamp


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-034")
async def test_cleanup_expired_deletes_old_violations(
    config: MonitoringConfig,
    mock_repository: MockRepository,
) -> None:
    """Test cleanup_expired deletes raw violations older than retention period.

    Verifies that violations older than 90 days (default) are deleted,
    while recent ones are preserved.
    """
    now = datetime.now(tz=timezone.utc)
    old_timestamp = now - timedelta(days=120)  # Older than 90 days
    recent_timestamp = now - timedelta(days=14)  # Within 90 days

    # Add old and recent violations
    mock_repository.violations = [
        {
            "id": uuid.uuid4(),
            "contract_name": "orders_v1",
            "contract_version": "1.0.0",
            "violation_type": "freshness",
            "severity": "high",
            "message": "Data stale",
            "element": None,
            "expected_value": None,
            "actual_value": None,
            "timestamp": old_timestamp,
            "affected_consumers": [],
            "check_duration_seconds": 2.0,
            "metadata": {},
        },
        {
            "id": uuid.uuid4(),
            "contract_name": "orders_v1",
            "contract_version": "1.0.0",
            "violation_type": "freshness",
            "severity": "high",
            "message": "Data stale",
            "element": None,
            "expected_value": None,
            "actual_value": None,
            "timestamp": recent_timestamp,
            "affected_consumers": [],
            "check_duration_seconds": 2.0,
            "metadata": {},
        },
    ]

    # Run cleanup through ContractMonitor
    monitor = ContractMonitor(config=config, repository=mock_repository)
    deleted_count = await monitor.cleanup_expired(retention_days=90)

    # Verify old violation was deleted, recent one preserved
    assert deleted_count == 1
    assert len(mock_repository.violations) == 1
    assert mock_repository.violations[0]["timestamp"] == recent_timestamp


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-034")
async def test_cleanup_expired_preserves_daily_aggregates(
    config: MonitoringConfig,
    mock_repository: MockRepository,
) -> None:
    """Test cleanup_expired does NOT delete daily aggregates (indefinite retention).

    Verifies that daily aggregates are preserved regardless of age,
    implementing the indefinite retention policy for aggregates.
    """
    now = datetime.now(tz=timezone.utc)
    very_old_date = now - timedelta(days=365)  # 1 year old

    # Add very old aggregate
    mock_repository.daily_aggregates = [
        {
            "contract_name": "orders_v1",
            "check_type": "freshness",
            "date": very_old_date,
            "total_checks": 100,
            "passed_checks": 99,
            "failed_checks": 1,
            "error_checks": 0,
            "avg_duration_seconds": 1.2,
            "violation_count": 1,
        },
    ]

    # Store initial count
    initial_count = len(mock_repository.daily_aggregates)

    # Run cleanup through ContractMonitor
    monitor = ContractMonitor(config=config, repository=mock_repository)
    deleted_count = await monitor.cleanup_expired(retention_days=90)

    # Verify aggregate was NOT deleted
    assert len(mock_repository.daily_aggregates) == initial_count
    assert mock_repository.daily_aggregates[0]["date"] == very_old_date
    # Only raw results and violations should be deleted (0 in this case)
    assert deleted_count == 0


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-034")
async def test_cleanup_expired_deletes_both_results_and_violations(
    config: MonitoringConfig,
    mock_repository: MockRepository,
) -> None:
    """Test cleanup_expired deletes both old results and violations together.

    Verifies that cleanup_expired correctly counts and deletes both
    check results and violations in a single operation.
    """
    now = datetime.now(tz=timezone.utc)
    old_timestamp = now - timedelta(days=100)

    # Add both old results and violations
    mock_repository.check_results = [
        {
            "id": uuid.uuid4(),
            "contract_name": "orders_v1",
            "check_type": "freshness",
            "status": "fail",
            "duration_seconds": 2.0,
            "timestamp": old_timestamp,
            "details": {},
        },
        {
            "id": uuid.uuid4(),
            "contract_name": "customers_v1",
            "check_type": "quality",
            "status": "pass",
            "duration_seconds": 1.5,
            "timestamp": old_timestamp,
            "details": {},
        },
    ]

    mock_repository.violations = [
        {
            "id": uuid.uuid4(),
            "contract_name": "orders_v1",
            "contract_version": "1.0.0",
            "violation_type": "freshness",
            "severity": "high",
            "message": "Stale data",
            "element": None,
            "expected_value": None,
            "actual_value": None,
            "timestamp": old_timestamp,
            "affected_consumers": [],
            "check_duration_seconds": 2.0,
            "metadata": {},
        },
        {
            "id": uuid.uuid4(),
            "contract_name": "customers_v1",
            "contract_version": "2.0.0",
            "violation_type": "quality",
            "severity": "medium",
            "message": "Quality issue",
            "element": None,
            "expected_value": None,
            "actual_value": None,
            "timestamp": old_timestamp,
            "affected_consumers": [],
            "check_duration_seconds": 1.5,
            "metadata": {},
        },
    ]

    # Run cleanup through ContractMonitor
    monitor = ContractMonitor(config=config, repository=mock_repository)
    deleted_count = await monitor.cleanup_expired(retention_days=90)

    # Verify all old records were deleted
    assert deleted_count == 4  # 2 check results + 2 violations
    assert len(mock_repository.check_results) == 0
    assert len(mock_repository.violations) == 0


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-034")
async def test_cleanup_expired_with_custom_retention_days(
    config: MonitoringConfig,
    mock_repository: MockRepository,
) -> None:
    """Test cleanup_expired respects custom retention_days parameter.

    Verifies that cleanup_expired can be configured with custom retention
    periods different from the default 90 days.
    """
    now = datetime.now(tz=timezone.utc)
    too_old_timestamp = now - timedelta(days=31)  # Older than 30 days
    within_retention = now - timedelta(days=15)  # Within 30 days

    # Add check results at different ages
    mock_repository.check_results = [
        {
            "id": uuid.uuid4(),
            "contract_name": "orders_v1",
            "check_type": "freshness",
            "status": "pass",
            "duration_seconds": 1.5,
            "timestamp": too_old_timestamp,
            "details": {},
        },
        {
            "id": uuid.uuid4(),
            "contract_name": "orders_v1",
            "check_type": "freshness",
            "status": "pass",
            "duration_seconds": 1.5,
            "timestamp": within_retention,
            "details": {},
        },
    ]

    # Run cleanup through ContractMonitor with 30-day retention
    monitor = ContractMonitor(config=config, repository=mock_repository)
    deleted_count = await monitor.cleanup_expired(retention_days=30)

    # Verify only the too-old result was deleted
    assert deleted_count == 1
    assert len(mock_repository.check_results) == 1
    assert mock_repository.check_results[0]["timestamp"] == within_retention


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-034")
async def test_cleanup_expired_empty_database(
    config: MonitoringConfig,
    mock_repository: MockRepository,
) -> None:
    """Test cleanup_expired handles empty database gracefully.

    Verifies that cleanup_expired returns 0 when there are no records to delete.
    """
    # Start with empty repository
    assert len(mock_repository.check_results) == 0
    assert len(mock_repository.violations) == 0

    # Run cleanup through ContractMonitor
    monitor = ContractMonitor(config=config, repository=mock_repository)
    deleted_count = await monitor.cleanup_expired(retention_days=90)

    # Verify it handled empty case
    assert deleted_count == 0
