"""Contract-layer exception types.

These errors make contract, adapter, and execution-context failures distinct
from generic runtime exceptions.
"""

from __future__ import annotations


class ContractError(ValueError):
    """Base class for contract-layer failures."""


class ContractGenerationError(ContractError):
    """Raised when canonical contract facts cannot produce valid bindings."""


class ContractViolationError(ContractError):
    """Raised when a consumer violates a canonical contract."""


class ExecutionContextMismatch(ContractViolationError):
    """Raised when code runs under an execution context it was not written for."""
