# Security Remediation Plan - Epic 9B Helm Charts

**Date:** 2026-02-01
**Branch:** 9b-helm-deployment
**Status:** Ready for Implementation

---

## Executive Summary

Security review identified **3 confirmed vulnerabilities** requiring remediation:

| Priority | Issue | Severity | Effort |
|----------|-------|----------|--------|
| P1 | PostgreSQL hardcoded default password | HIGH | 2 hours |
| P2 | Polaris anonymous access in production | MEDIUM | 1 hour |
| P3 | RBAC excessive secret read permissions | MEDIUM | 1 hour |

**Total Estimated Effort:** 4-5 hours

---

## Vulnerability 1: PostgreSQL Hardcoded Default Password

### Problem

`charts/floe-platform/templates/secret-postgresql.yaml` falls back to password "floe" when not explicitly set:

```yaml
postgresql-password: {{ .Values.postgresql.auth.password | default "floe" | b64enc }}
```

### Root Cause

- Default in `values.yaml` is empty string: `password: ""`
- Template uses `| default "floe"` as fallback
- No validation prevents deploying production with weak password

### Remediation (Defense in Depth)

#### Step 1: Update Template with Environment Check

**File:** `charts/floe-platform/templates/secret-postgresql.yaml`

```yaml
{{- if and (ne .Values.global.environment "dev") (not .Values.postgresql.auth.existingSecret) }}
{{- if or (not .Values.postgresql.auth.password) (lt (len .Values.postgresql.auth.password) 16) }}
{{- fail "SECURITY: Production/staging requires postgresql.auth.password (min 16 chars) or postgresql.auth.existingSecret" }}
{{- end }}
{{- end }}
data:
  {{- $password := .Values.postgresql.auth.password | default (include "floe-platform.randomPassword" .) }}
  postgresql-password: {{ $password | b64enc | quote }}
```

#### Step 2: Add Schema Validation

**File:** `charts/floe-platform/values.schema.json`

Add conditional validation rule:

```json
{
  "if": {
    "properties": {
      "global": {
        "properties": {
          "environment": { "enum": ["prod", "staging"] }
        }
      }
    }
  },
  "then": {
    "properties": {
      "postgresql": {
        "properties": {
          "auth": {
            "oneOf": [
              { "required": ["existingSecret"] },
              {
                "properties": {
                  "password": { "type": "string", "minLength": 16 }
                },
                "required": ["password"]
              }
            ]
          }
        }
      }
    }
  }
}
```

#### Step 3: Update Production Values

**File:** `charts/floe-platform/values-prod.yaml`

Add commented example:

```yaml
postgresql:
  auth:
    # REQUIRED: Use one of:
    # Option 1: External Secrets Operator (recommended)
    existingSecret: "floe-postgresql-external"
    # Option 2: Explicit password (min 16 chars)
    # password: "your-secure-password-here"
```

### Verification

```bash
# Should FAIL (no password for prod)
helm template test charts/floe-platform --set global.environment=prod 2>&1 | grep -q "SECURITY"

# Should PASS (with existingSecret)
helm template test charts/floe-platform --set global.environment=prod --set postgresql.auth.existingSecret=my-secret

# Should PASS (dev with default)
helm template test charts/floe-platform --set global.environment=dev
```

---

## Vulnerability 2: Polaris Anonymous Access in Production

### Problem

`ALLOW_ANONYMOUS_ACCESS: true` is default and not overridden in production values.

### Root Cause

- `values.yaml` enables anonymous access for developer convenience
- `values-prod.yaml` does not override this security-critical setting

### Remediation

#### Step 1: Override in Production Values

**File:** `charts/floe-platform/values-prod.yaml`

Add at the end of the polaris section:

```yaml
polaris:
  # ... existing config ...
  config:
    features:
      ALLOW_ANONYMOUS_ACCESS: false
      ALLOW_TABLE_LOCATION_OVERLAP: false
      ALLOW_EXTERNAL_METADATA_FILE_LOCATION: false
```

#### Step 2: Override in Staging Values

**File:** `charts/floe-platform/values-staging.yaml`

```yaml
polaris:
  config:
    features:
      ALLOW_ANONYMOUS_ACCESS: false
```

#### Step 3: Add Schema Validation

**File:** `charts/floe-platform/values.schema.json`

```json
{
  "if": {
    "properties": {
      "global": {
        "properties": {
          "environment": { "enum": ["prod", "staging"] }
        }
      }
    }
  },
  "then": {
    "properties": {
      "polaris": {
        "properties": {
          "config": {
            "properties": {
              "features": {
                "properties": {
                  "ALLOW_ANONYMOUS_ACCESS": { "const": false }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### Verification

```bash
# Render prod and check for anonymous access
helm template test charts/floe-platform \
  --values charts/floe-platform/values-prod.yaml \
  | grep -A5 "ALLOW_ANONYMOUS_ACCESS" | grep "false"
```

---

## Vulnerability 3: RBAC Excessive Secret Read Permissions

### Problem

Role grants `get`, `list`, `watch` on ALL secrets in namespace, but Dagster doesn't need this.

### Root Cause

- Over-permissioning from initial chart development
- Dagster uses volume mounts for secrets, not API access
- Pattern copied without validation of actual requirements

### Remediation

#### Step 1: Update Role Template

**File:** `charts/floe-platform/templates/role.yaml`

Replace:

```yaml
# REMOVE THIS BLOCK
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list", "watch"]
```

With:

```yaml
# ConfigMaps only - Dagster needs these for workspace config
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list"]

# Explicit pod subresources for log streaming
- apiGroups: [""]
  resources: ["pods/log", "pods/status"]
  verbs: ["get", "list"]

# Job status for run tracking
- apiGroups: ["batch"]
  resources: ["jobs/status"]
  verbs: ["get", "list"]
```

### Verification

```bash
# Render and verify no secret permissions
helm template test charts/floe-platform | grep -A3 "resources.*secrets" | wc -l
# Expected: 0

# Test Dagster functionality after deployment
kubectl -n floe-test exec deploy/dagster-webserver -- dagster run list
```

---

## Implementation Checklist

### Pre-Implementation

- [ ] Create feature branch: `git checkout -b security/helm-remediation`
- [ ] Read all three vulnerability sections above

### Phase 1: PostgreSQL Password (P1)

- [ ] Update `charts/floe-platform/templates/secret-postgresql.yaml`
- [ ] Add helper for random password generation in `_helpers.tpl`
- [ ] Update `charts/floe-platform/values.schema.json`
- [ ] Update `charts/floe-platform/values-prod.yaml`
- [ ] Run verification commands
- [ ] Commit: `fix(security): require strong PostgreSQL password in production`

### Phase 2: Polaris Anonymous Access (P2)

- [ ] Update `charts/floe-platform/values-prod.yaml`
- [ ] Update `charts/floe-platform/values-staging.yaml`
- [ ] Update `charts/floe-platform/values.schema.json`
- [ ] Run verification commands
- [ ] Commit: `fix(security): disable Polaris anonymous access in production`

### Phase 3: RBAC Permissions (P3)

- [ ] Update `charts/floe-platform/templates/role.yaml`
- [ ] Run verification commands
- [ ] Test Dagster functionality in Kind cluster
- [ ] Commit: `fix(security): remove unnecessary RBAC secret permissions`

### Post-Implementation

- [ ] Run full Helm lint: `make helm-lint`
- [ ] Run integration tests: `make helm-test`
- [ ] Update CHANGELOG or release notes
- [ ] Create PR for security review

---

## Test Matrix

| Test | Before | After | Command |
|------|--------|-------|---------|
| Prod deploy without password | ✅ Allowed | ❌ Fails | `helm template --set global.environment=prod` |
| Dev deploy without password | ✅ Allowed | ✅ Allowed | `helm template --set global.environment=dev` |
| Polaris anonymous in prod | ✅ Enabled | ❌ Disabled | Check configmap output |
| Secret API access in role | ✅ Granted | ❌ Removed | Check role output |
| Dagster run creation | ✅ Works | ✅ Works | `dagster run list` |

---

## Rollback Plan

If issues occur after deployment:

```bash
# Quick rollback - revert to previous chart version
helm rollback floe-platform <previous-revision> -n floe

# Or revert git commits
git revert HEAD~3..HEAD  # Revert last 3 commits
```

---

## References

- Security Review: `/Users/dmccarthy/.claude/projects/-Users-dmccarthy-Projects-floe/*/tool-results/*.txt`
- Dagster K8sRunLauncher docs: https://docs.dagster.io/deployment/guides/kubernetes
- Polaris security docs: https://polaris.apache.org/security/
- Kubernetes RBAC best practices: https://kubernetes.io/docs/concepts/security/rbac-good-practices/
