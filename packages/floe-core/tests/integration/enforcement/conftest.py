"""Integration test fixtures for the policy enforcement module.

This module provides fixtures specific to enforcement integration tests, which:
- Run in K8s (Kind cluster) for production parity
- Test real compilation pipeline integration
- Validate end-to-end enforcement behavior

Task: T004 (part of test directory structure)
Requirements: FR-002 (Pipeline integration), US1 (Compile-time enforcement)

For shared fixtures across all test tiers, see ../conftest.py.
"""

from __future__ import annotations
