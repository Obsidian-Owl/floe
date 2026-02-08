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
from floe_core.contracts.monitoring.checks.freshness import FreshnessCheck
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
    ) -> None:
        """Initialize the contract monitor.

        Args:
            config: Global monitoring configuration. Individual contracts may
                override via RegisteredContract.monitoring_overrides.
            alert_router: Optional AlertRouter for dispatching violations to
                alert channels. If None, violations are logged but not routed.
        """
        self._config = config
        self._alert_router = alert_router
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

        return result
