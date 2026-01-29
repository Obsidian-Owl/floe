"""Shared fixtures and helpers for lineage tests."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def _run(coro: Any) -> Any:
    """Run an async coroutine synchronously for testing."""
    return asyncio.run(coro)
