"""End-to-end test suite for demo pipeline workflow.

DEPRECATED: Tests have been moved to specialized modules:
- test_platform_bootstrap.py: Platform initialization and configuration
- test_helm_workflow.py: Helm chart deployment validation

The comprehensive E2E tests validating the complete floe platform workflow
(compile → deploy → run → validate) are implemented in the modules above.

Requirements covered:
- E2E-001: Full pipeline workflow validation
- E2E-002: Platform services integration
- E2E-003: Catalog integration

See test_platform_bootstrap.py and test_helm_workflow.py for implementations.
"""

from __future__ import annotations

# Tests have been consolidated into:
# - tests/e2e/test_platform_bootstrap.py - Platform setup and services
# - tests/e2e/test_helm_workflow.py - Helm deployment workflows

__all__: list[str] = []
