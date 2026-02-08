"""ContractMonitor — orchestrates contract validation checks.

This module implements the main ContractMonitor class responsible for:
- Registering/unregistering contracts for monitoring
- Dispatching validation checks based on check type
- Managing monitor lifecycle (start/stop)
- Providing health check visibility
- Routing violations to alert channels via AlertRouter

Tasks: T029, T030, T031, T045 (Epic 3D)
Requirements: FR-001 through FR-010, FR-028
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import structlog

from floe_core.contracts.monitoring.alert_router import AlertRouter
from floe_core.contracts.monitoring.checks.availability import AvailabilityCheck
from floe_core.contracts.monitoring.checks.freshness import FreshnessCheck
from floe_core.contracts.monitoring.checks.quality import QualityCheck
from floe_core.contracts.monitoring.checks.schema_drift import SchemaDriftCheck
from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.violations import (
    CheckResult,
    CheckStatus,
    ViolationType,
)

logger = structlog.get_logger(__name__)


class ContractMonitor:
    """Orchestrates contract monitoring checks.

    The ContractMonitor maintains a registry of contracts and dispatches
    validation checks to the appropriate check implementation. It supports
    per-contract monitoring config overrides.

    Attributes:
        registered_contracts: Dictionary of registered contracts (returns copy).
        is_running: Whether the monitor is actively running.

    Example:
        >>> config = MonitoringConfig()
        >>> monitor = ContractMonitor(config=config)
        >>> monitor.register_contract(contract)
        >>> await monitor.start()
        >>> result = await monitor.run_check("orders_v1", ViolationType.FRESHNESS)
        >>> await monitor.stop()
    """

    def __init__(
        self,
        config: MonitoringConfig,
        alert_router: AlertRouter | None = None,
        quality_plugin: Any | None = None,
        compute_plugin: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        """Initialize the contract monitor.

        Args:
            config: Global monitoring configuration. Individual contracts may
                override via RegisteredContract.monitoring_overrides.
            alert_router: Optional AlertRouter for dispatching violations to
                alert channels. If None, violations are logged but not routed.
            quality_plugin: Optional quality plugin implementing the QualityPlugin
                protocol (duck-typed). If None, quality checks are SKIPPED.
            compute_plugin: Optional compute plugin implementing the ComputePlugin
                protocol (duck-typed, has validate_connection() method). If None,
                availability checks are SKIPPED.
            repository: Optional repository for persistence (duck-typed to avoid
                hard import dependency on SQLAlchemy in non-DB contexts). If None,
                check results and violations are not persisted.
        """
        self._config = config
        self._alert_router = alert_router
        self._quality_plugin = quality_plugin
        self._compute_plugin = compute_plugin
        self._repository = repository
        self._contracts: dict[str, RegisteredContract] = {}
        self._is_running: bool = False
        self._log = logger.bind(component="contract_monitor")

    @property
    def registered_contracts(self) -> dict[str, RegisteredContract]:
        """Get copy of registered contracts.

        Returns:
            Dictionary mapping contract_name to RegisteredContract.
            Returns a copy to prevent external mutation.
        """
        return dict(self._contracts)

    @property
    def is_running(self) -> bool:
        """Check if monitor is running.

        Returns:
            True if monitor has been started and not yet stopped.
        """
        return self._is_running

    def register_contract(self, contract: RegisteredContract) -> None:
        """Register a contract for monitoring.

        Args:
            contract: Contract to register.

        Raises:
            ValueError: If a contract with this name is already registered.
        """
        if contract.contract_name in self._contracts:
            msg = f"Contract '{contract.contract_name}' is already registered"
            raise ValueError(msg)

        self._contracts[contract.contract_name] = contract
        self._log.info(
            "contract_registered",
            contract_name=contract.contract_name,
            active=contract.active,
        )

    def unregister_contract(self, contract_name: str) -> None:
        """Unregister a contract from monitoring.

        Args:
            contract_name: Name of contract to unregister.

        Raises:
            KeyError: If contract is not found.
        """
        if contract_name not in self._contracts:
            msg = f"Contract '{contract_name}' is not found"
            raise KeyError(msg)

        del self._contracts[contract_name]
        self._log.info("contract_unregistered", contract_name=contract_name)

    async def start(self) -> None:
        """Start the monitor.

        Sets is_running to True. In a full implementation, this would
        start the CheckScheduler for periodic checks.
        """
        self._is_running = True
        self._log.info("monitor_started", registered_count=len(self._contracts))

    async def stop(self) -> None:
        """Stop the monitor.

        Sets is_running to False. In a full implementation, this would
        cancel all scheduled checks via CheckScheduler.
        """
        self._is_running = False
        self._log.info("monitor_stopped")

    def health_check(self) -> dict[str, Any]:
        """Check monitor health status.

        Returns:
            Dictionary with status, registered_contracts count, is_running.
        """
        return {
            "status": "healthy",
            "registered_contracts": len(self._contracts),
            "is_running": self._is_running,
        }

    async def run_check(
        self,
        contract_name: str,
        check_type: ViolationType,
    ) -> CheckResult:
        """Run a specific check on a contract.

        Dispatches to the appropriate check implementation based on check_type.
        Uses per-contract config override if present, otherwise global config.
        If a violation is detected and an AlertRouter is configured, routes
        the violation to alert channels.

        Args:
            contract_name: Name of contract to check.
            check_type: Type of validation check to run.

        Returns:
            CheckResult with check outcome.

        Raises:
            KeyError: If contract is not registered.
        """
        if contract_name not in self._contracts:
            msg = f"Contract '{contract_name}' is not registered"
            raise KeyError(msg)

        contract = self._contracts[contract_name]

        # Use per-contract config override if present
        check_config = (
            contract.monitoring_overrides
            if contract.monitoring_overrides is not None
            else self._config
        )

        self._log.debug(
            "running_check",
            contract_name=contract_name,
            check_type=check_type.value,
        )

        # Dispatch to appropriate check implementation
        result: CheckResult | None = None

        if check_type == ViolationType.FRESHNESS:
            check = FreshnessCheck()
            result = await check.execute(contract=contract, config=check_config)

        elif check_type == ViolationType.SCHEMA_DRIFT:
            drift_check = SchemaDriftCheck()
            result = await drift_check.execute(contract=contract, config=check_config)

        elif check_type == ViolationType.QUALITY:
            quality_check = QualityCheck(quality_plugin=self._quality_plugin)
            result = await quality_check.execute(contract=contract, config=check_config)

        elif check_type == ViolationType.AVAILABILITY:
            avail_check = AvailabilityCheck(compute_plugin=self._compute_plugin)
            result = await avail_check.execute(contract=contract, config=check_config)

        else:
            # Unimplemented check types return ERROR
            now = datetime.now(tz=timezone.utc)
            start = time.monotonic()
            duration = time.monotonic() - start

            self._log.warning(
                "check_not_implemented",
                contract_name=contract_name,
                check_type=check_type.value,
            )

            result = CheckResult(
                contract_name=contract_name,
                check_type=check_type,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={"error": f"Check type not yet implemented: {check_type.value}"},
            )

        # Route violations to alert channels if AlertRouter is configured
        if result.violation is not None and self._alert_router is not None:
            await self._alert_router.route(result.violation)

        # Persist results if repository is available
        if self._repository is not None:
            try:
                await self._persist_result(result)
            except Exception as e:
                self._log.error(
                    "persist_result_failed",
                    contract_name=contract_name,
                    error=str(e),
                )

        return result

    async def _persist_result(self, result: CheckResult) -> None:
        """Persist check result and any violation to the repository.

        Fire-and-forget: errors are logged but never propagated.

        Args:
            result: CheckResult to persist.
        """
        # Type guard: caller already checked repository is not None
        assert self._repository is not None

        await self._repository.save_check_result({
            "id": result.id,
            "contract_name": result.contract_name,
            "check_type": result.check_type.value,
            "status": result.status.value,
            "duration_seconds": result.duration_seconds,
            "timestamp": result.timestamp,
            "details": result.details,
        })

        if result.violation is not None:
            await self._repository.save_violation({
                "contract_name": result.violation.contract_name,
                "contract_version": result.violation.contract_version,
                "violation_type": result.violation.violation_type.value,
                "severity": result.violation.severity.value,
                "message": result.violation.message,
                "element": result.violation.element,
                "expected_value": result.violation.expected_value,
                "actual_value": result.violation.actual_value,
                "timestamp": result.violation.timestamp,
                "affected_consumers": result.violation.affected_consumers,
                "check_duration_seconds": result.violation.check_duration_seconds,
                "metadata": dict(result.violation.metadata),
            })

    async def discover_contracts(self) -> int:
        """Discover and register contracts on cold start.

        Recovery strategy:
        1. If repository available, load from database (primary source)
        2. If DB empty or unavailable, log warning (catalog discovery
           requires CatalogPlugin integration from a future phase)

        Returns:
            Number of contracts discovered and registered.
        """
        discovered = 0

        if self._repository is not None:
            try:
                contracts = await self._repository.get_registered_contracts(active_only=True)
                for contract_data in contracts:
                    try:
                        contract = RegisteredContract(
                            contract_name=contract_data["contract_name"],
                            contract_version=contract_data["contract_version"],
                            contract_data=contract_data["contract_data"],
                            connection_config=contract_data["connection_config"],
                            monitoring_overrides=contract_data.get("monitoring_overrides"),
                            registered_at=contract_data["registered_at"],
                            last_check_times=contract_data.get("last_check_times", {}),
                            active=contract_data.get("active", True),
                        )
                        if contract.contract_name not in self._contracts:
                            self._contracts[contract.contract_name] = contract
                            discovered += 1
                    except Exception as e:
                        self._log.warning(
                            "contract_discovery_error",
                            contract_name=contract_data.get("contract_name", "unknown"),
                            error=str(e),
                        )
            except Exception as e:
                self._log.error("contract_discovery_db_failed", error=str(e))

        self._log.info("contract_discovery_completed", discovered=discovered)
        return discovered
