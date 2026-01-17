"""Unit test fixtures for the CLI module.

This module provides fixtures specific to CLI unit tests, which:
- Run without external services (no K8s, no databases)
- Use mocks/fakes for compilation dependencies
- Test argument parsing and command execution
- Execute quickly (< 1s per test)

For shared fixtures across all test tiers, see ../conftest.py.
"""

from __future__ import annotations
