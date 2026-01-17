"""Unit test fixtures for the compilation module.

This module provides fixtures specific to compilation unit tests, which:
- Run without external services (no K8s, no databases)
- Use mocks/fakes for all plugin dependencies
- Execute quickly (< 1s per test)

For shared fixtures across all test tiers, see ../conftest.py.
"""

from __future__ import annotations
