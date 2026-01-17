"""Testing utilities for agent-memory.

This module provides reusable test utilities that can be imported by test files.
Placing these in the main package (not tests/) ensures they're importable.

Note: This module is for test utilities, not production code.
"""

from __future__ import annotations

import uuid


def generate_test_dataset_name(base: str = "test") -> str:
    """Generate unique test dataset name with prefix.

    All integration test datasets use this format to:
    1. Avoid polluting production datasets
    2. Enable cleanup via test_ prefix matching
    3. Prevent test interference via unique suffixes

    Args:
        base: Base name for the dataset (default: "test").

    Returns:
        Unique dataset name in format: test_{base}_{uuid8}

    Example:
        >>> name = generate_test_dataset_name("architecture")
        >>> name  # "test_architecture_a1b2c3d4"
    """
    suffix = uuid.uuid4().hex[:8]
    return f"test_{base}_{suffix}"
