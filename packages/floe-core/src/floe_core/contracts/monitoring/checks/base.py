"""Base check ABC for contract monitoring check implementations.

This module defines the abstract base class that all monitoring checks
(freshness, schema drift, quality, availability) must implement.

Tasks: T014 (Epic 3D)
Requirements: FR-003, FR-006

Example:
    Implementing a custom check::

        class FreshnessCheck(BaseCheck):
            @property
            def check_type(self) -> ViolationType:
                return ViolationType.FRESHNESS

            async def execute(
                self,
                contract: RegisteredContract,
                config: MonitoringConfig,
            ) -> CheckResult:
                # Perform freshness check...
                ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.violations import CheckResult, ViolationType


class BaseCheck(ABC):
    """Abstract base class for contract monitoring checks.

    Each check type (freshness, schema drift, quality, availability)
    inherits from this class and implements the execute() method.

    The ContractMonitor dispatches checks based on check_type and
    ensures no overlapping executions for the same contract/check
    combination (FR-006).

    Abstract Properties:
        check_type: The ViolationType this check detects.

    Abstract Methods:
        execute: Run the check against a registered contract.
    """

    @property
    @abstractmethod
    def check_type(self) -> ViolationType:
        """The type of violation this check detects.

        Used by ContractMonitor for dispatch and scheduling.

        Returns:
            The ViolationType enum value for this check.
        """
        ...

    @abstractmethod
    async def execute(
        self,
        contract: RegisteredContract,
        config: MonitoringConfig,
    ) -> CheckResult:
        """Execute this monitoring check against a registered contract.

        Implementations should:
        1. Retrieve the relevant data (e.g., table metadata, schema, metrics)
        2. Compare against the contract's SLA/schema/quality expectations
        3. Return a CheckResult with status PASS or FAIL
        4. Include a ContractViolationEvent in the result if status is FAIL

        The check MUST complete within config.check_timeout_seconds (FR-022).
        If a timeout occurs, return CheckResult with status ERROR.

        Args:
            contract: The registered contract to check.
            config: Global monitoring configuration (may be overridden per-contract).

        Returns:
            CheckResult recording the check outcome.

        Raises:
            No exceptions should be raised. Errors should be captured
            in the CheckResult with status ERROR.
        """
        ...
