"""Unit test configuration for floe-iceberg.

Unit tests use mock plugins and do not require external services.
Fixtures are automatically discovered from the parent conftest.py.

Note:
    No __init__.py files in test directories - pytest uses importlib mode.
"""

from __future__ import annotations

# Fixtures from parent conftest.py are automatically discovered by pytest.
# No explicit imports needed - pytest handles fixture discovery.
