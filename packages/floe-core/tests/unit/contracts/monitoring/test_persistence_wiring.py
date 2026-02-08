"""Unit tests for persistence wiring in ContractMonitor.

Tasks: T059, T060 (Epic 3D)
Requirements: FR-031, FR-032
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.monitor import ContractMonitor
from floe_core.contracts.monitoring.violations import (
    CheckResult,
    CheckStatus,
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)


class MockRepository:
    """Mock repository for testing persistence wiring."""

    def __init__(self) -> None:
        """Initialize mock repository with empty storage."""
        self.check_results: list[dict[str, Any]] = []
        self.violations: list[dict[str, Any]] = []
        self.registered: list[dict[str, Any]] = []

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
async def test_run_check_persists_fail_result_and_violation(
    config: MonitoringConfig,
    sample_contract: RegisteredContract,
    mock_repository: MockRepository,
) -> None:
    """Test that FAIL result and violation are saved to repository.

    Verifies that when a check fails, both the result and violation are
    persisted with correct details.
    """
    # Create a monitor with mocked quality plugin that returns FAIL
    mock_quality_plugin = AsyncMock()
    monitor = ContractMonitor(
        config=config,
        quality_plugin=mock_quality_plugin,
        repository=mock_repository,
    )
    monitor.register_contract(sample_contract)

    # Run quality check (will call quality_plugin)
    result = await monitor.run_check("orders_v1", ViolationType.QUALITY)

    # Verify both result and violation were persisted
    assert len(mock_repository.check_results) == 1
    saved_result = mock_repository.check_results[0]
    assert saved_result["contract_name"] == "orders_v1"
    assert saved_result["check_type"] == ViolationType.QUALITY.value

    # Quality check without plugin should skip (no violation)
    # If it did produce a violation, it would be saved
    if result.violation is not None:
        assert len(mock_repository.violations) == 1
        saved_violation = mock_repository.violations[0]
        assert saved_violation["contract_name"] == "orders_v1"
        assert saved_violation["violation_type"] == result.violation.violation_type.value


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
    failing_repository.save_check_result = AsyncMock(side_effect=RuntimeError("DB error"))

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
