# Testing Conventions

Quick reference for running and writing tests in the floe monorepo.

## Running Tests

### From Repository Root (Required)

Tests must be run from the repository root with PYTHONPATH set:

```bash
# Run all tests (excluding E2E)
PYTHONPATH=. pytest tests/ packages/ --ignore=tests/e2e

# Run specific package tests
PYTHONPATH=. pytest packages/floe-core/tests/

# Run contract tests only
PYTHONPATH=. pytest tests/contract/
```

### Test Categories

| Category | Location | Markers | Requirements |
|----------|----------|---------|--------------|
| Unit | `packages/*/tests/unit/` | None | None |
| Integration | `packages/*/tests/integration/` | `@pytest.mark.integration` | External services |
| Contract | `tests/contract/` | `@pytest.mark.requirement()` | None |
| E2E | `tests/e2e/` | `@pytest.mark.e2e` | Kind cluster |

## Pytest Markers

Available markers (defined in root `pyproject.toml`):

```python
@pytest.mark.requirement("FR-001")  # Requirement traceability
@pytest.mark.slow                    # Tests > 1 second
@pytest.mark.integration             # Requires external services
@pytest.mark.e2e                     # Full platform tests
@pytest.mark.contract                # Cross-package contracts
```

### Running by Marker

```bash
# Unit tests only (fast)
pytest -m "not integration and not e2e"

# Integration tests
pytest -m integration

# Specific requirement
pytest -m "requirement"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLOE_DISABLE_BROWSER_OAUTH` | `false` | Prevent browser OAuth in tests |
| `FLOE_OIDC_TOKEN_MAX_RETRIES` | `3` | OIDC token retry attempts |

### CI/CD Configuration

```yaml
# GitHub Actions
env:
  FLOE_DISABLE_BROWSER_OAUTH: "true"
permissions:
  id-token: write  # For keyless signing
```

## Conftest Organization

| Location | Scope | Use For |
|----------|-------|---------|
| `tests/conftest.py` | Root tests | Cross-package fixtures |
| `packages/*/tests/conftest.py` | Package | Package-specific fixtures |
| `packages/*/tests/unit/conftest.py` | Unit tests | Mock factories |

### Fixture Best Practices

```python
# Package-level fixture (tests/conftest.py)
@pytest.fixture(scope="session")
def expensive_resource():
    """Session-scoped for expensive setup."""
    yield resource

# Test-level fixture (tests/unit/conftest.py)
@pytest.fixture
def mock_client():
    """Function-scoped for isolation."""
    return MagicMock()
```

## E2E Test Requirements

E2E tests require a Kind cluster with platform services:

```bash
# Start Kind cluster
make kind-up

# Run E2E tests
PYTHONPATH=. pytest tests/e2e/ -v

# Stop cluster
make kind-down
```

## Common Issues

### Import Errors

If you see `ModuleNotFoundError: No module named 'testing'`:

```bash
# Wrong: Running from package directory
cd packages/floe-core && pytest tests/

# Right: Run from repo root
cd /path/to/floe && PYTHONPATH=. pytest packages/floe-core/tests/
```

### Browser OAuth Prompts

If sigstore triggers browser auth during tests:

```bash
# Disable browser OAuth fallback
FLOE_DISABLE_BROWSER_OAUTH=true pytest
```
