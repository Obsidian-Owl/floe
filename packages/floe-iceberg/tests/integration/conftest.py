"""Integration test configuration for floe-iceberg.

Integration tests require real services (Polaris, S3/LocalStack) and
inherit from IntegrationTestBase for service lifecycle management.

Note:
    No __init__.py files in test directories - pytest uses importlib mode.
"""

from __future__ import annotations

# Integration tests will add service-specific fixtures here
# when integration tests are implemented in later tasks
