# Quickstart: Epic 3E — Governance Integration

**Date**: 2026-02-09

## Prerequisites

- floe CLI installed (`pip install floe-core`)
- All governance dependencies deployed (Epics 3A–3D, 7A–7C complete)
- Keycloak instance available (for OIDC RBAC)
- Kind cluster running (for integration tests)

## 1. Enable Governance in manifest.yaml

```yaml
# manifest.yaml
governance:
  policy_enforcement_level: warn  # or "strict" to block on violations

  # RBAC (compile-time identity validation)
  rbac:
    enabled: true
    required_role: platform-engineer
    allow_principal_fallback: true

  # Secret scanning
  secret_scanning:
    enabled: true
    exclude_patterns:
      - "**/tests/**"
      - "**/fixtures/**"

  # Network policies
  network_policies:
    enabled: true
    default_deny: true

  # Existing governance config (3A/3B/3C)
  naming:
    enforcement: warn
  quality_gates:
    minimum_test_coverage: 0.8
  data_contracts:
    enforcement: warn
```

## 2. Compile with Governance

```bash
# With OIDC token (production flow)
export FLOE_TOKEN=$(floe auth login --print-token)
floe compile

# With principal fallback (CI/CD flow)
floe compile --principal ci-pipeline

# Dry-run mode (preview violations without blocking)
floe compile --dry-run

# Allow secrets (downgrade to warnings)
floe compile --allow-secrets
```

## 3. Governance CLI Commands

```bash
# Check governance status
floe governance status

# Run audit (all checks, no artifact generation)
floe governance audit

# Export reports
floe governance report --format sarif -o governance-report.sarif
floe governance report --format json -o governance-report.json
floe governance report --format html -o governance-report.html
```

## 4. Secret Scanning Configuration

### Built-in Patterns

The built-in regex scanner detects:
- AWS Access Key IDs (`AKIA...`)
- Hardcoded passwords (`password = '...'`, `PASSWORD=...`)
- API keys/tokens (generic patterns)
- Private keys (RSA/EC BEGIN blocks)
- High-entropy strings (configurable threshold)

### Custom Patterns

```yaml
governance:
  secret_scanning:
    enabled: true
    custom_patterns:
      - name: "Internal API Token"
        pattern: "MYCO-[A-Za-z0-9]{32}"
        severity: error
      - name: "Internal DB Connection"
        pattern: "postgres://.*:.*@internal-db"
        severity: error
```

### Exclude Patterns

```yaml
governance:
  secret_scanning:
    exclude_patterns:
      - "**/tests/**"
      - "**/fixtures/**"
      - "**/*.md"
```

## 5. RBAC Flow

### Token-Based (Recommended)

```bash
# 1. Authenticate and get token
export FLOE_TOKEN=$(floe auth login --print-token)

# 2. Compile (token validated automatically)
floe compile
# ✓ RBAC: principal "alice@example.com" has role "platform-engineer"
```

### Principal Fallback (CI/CD)

```bash
# When OIDC is unavailable
export FLOE_PRINCIPAL=ci-pipeline
floe compile
# ✓ RBAC: using static principal "ci-pipeline" (OIDC unavailable)
```

## 6. Running Tests

```bash
# Unit tests (fast, no services)
make test-unit

# Integration tests (requires Kind cluster)
make test-integration

# Contract monitoring integration tests specifically
pytest packages/floe-core/tests/integration/contracts/monitoring/ -v

# All governance tests
pytest packages/floe-core/tests/unit/governance/ -v
pytest tests/contract/test_3e_governance_contract.py -v
```

## 7. Developing a Secret Scanner Plugin

```python
# my_scanner/plugin.py
from floe_core.plugins.secret_scanner import SecretScannerPlugin
from floe_core.governance.types import SecretFinding
from pathlib import Path

class GitleaksPlugin(SecretScannerPlugin):
    @property
    def name(self) -> str:
        return "gitleaks"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def scan_file(self, file_path: Path, content: str) -> list[SecretFinding]:
        # Call gitleaks binary or API
        ...

    def scan_directory(self, directory: Path, exclude_patterns: list[str] | None = None) -> list[SecretFinding]:
        # Scan entire directory
        ...

    def get_supported_patterns(self) -> list[str]:
        return ["aws-access-key", "github-token", "slack-webhook", ...]
```

Register via entry point:
```toml
# pyproject.toml
[project.entry-points."floe.secret_scanners"]
gitleaks = "my_scanner:GitleaksPlugin"
```

## 8. Enforcement Level Behavior

| Level | Violations | Compilation |
|-------|-----------|-------------|
| `off` | Not checked | Proceeds |
| `warn` | Reported as warnings | Proceeds |
| `strict` | Reported as errors | Blocked |

### 3-Tier Inheritance

```yaml
# Enterprise manifest (floor)
governance:
  policy_enforcement_level: warn
  rbac:
    enabled: true

# Domain manifest (can escalate, not relax)
governance:
  policy_enforcement_level: strict  # ✓ Escalated from warn
  # rbac.enabled: false  # ✗ Cannot relax enterprise floor
```
