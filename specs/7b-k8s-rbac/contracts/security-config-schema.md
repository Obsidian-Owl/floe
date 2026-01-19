# Contract: SecurityConfig Schema

**Feature**: Epic 7B - K8s RBAC Plugin System
**Version**: 1.0.0
**Date**: 2026-01-19

## Overview

This contract defines the `SecurityConfig` Pydantic schema that represents the `security` section of `manifest.yaml`. This schema is the input contract for RBAC manifest generation.

## Schema Location

`packages/floe-core/src/floe_core/schemas/security.py`

## JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SecurityConfig",
  "description": "Security section of manifest.yaml",
  "type": "object",
  "properties": {
    "rbac": {
      "$ref": "#/$defs/RBACConfig"
    },
    "pod_security": {
      "$ref": "#/$defs/PodSecurityLevelConfig"
    },
    "namespace_isolation": {
      "type": "string",
      "enum": ["strict", "permissive"],
      "default": "strict",
      "description": "Namespace isolation mode"
    }
  },
  "additionalProperties": false,
  "$defs": {
    "RBACConfig": {
      "type": "object",
      "properties": {
        "enabled": {
          "type": "boolean",
          "default": true,
          "description": "Enable RBAC generation"
        },
        "job_service_account": {
          "type": "string",
          "enum": ["auto", "manual"],
          "default": "auto",
          "description": "Service account creation mode"
        },
        "cluster_scope": {
          "type": "boolean",
          "default": false,
          "description": "Enable ClusterRole/ClusterRoleBinding generation"
        }
      },
      "additionalProperties": false
    },
    "PodSecurityLevelConfig": {
      "type": "object",
      "properties": {
        "jobs_level": {
          "type": "string",
          "enum": ["privileged", "baseline", "restricted"],
          "default": "restricted",
          "description": "PSS level for floe-jobs namespace"
        },
        "platform_level": {
          "type": "string",
          "enum": ["privileged", "baseline", "restricted"],
          "default": "baseline",
          "description": "PSS level for floe-platform namespace"
        }
      },
      "additionalProperties": false
    }
  }
}
```

## manifest.yaml Example

```yaml
# manifest.yaml
version: "1.0"
name: my-data-platform

security:
  rbac:
    enabled: true
    job_service_account: auto
    cluster_scope: false
  pod_security:
    jobs_level: restricted
    platform_level: baseline
  namespace_isolation: strict
```

## Validation Rules

### VR-001: Default Values

When `security` section is omitted, defaults apply:

| Field | Default |
|-------|---------|
| `rbac.enabled` | `true` |
| `rbac.job_service_account` | `"auto"` |
| `rbac.cluster_scope` | `false` |
| `pod_security.jobs_level` | `"restricted"` |
| `pod_security.platform_level` | `"baseline"` |
| `namespace_isolation` | `"strict"` |

### VR-002: Extra Fields Forbidden

```yaml
# INVALID - extra field rejected
security:
  rbac:
    enabled: true
    custom_field: value  # ValidationError: extra fields not permitted
```

### VR-003: Enum Validation

```yaml
# INVALID - invalid enum value
security:
  pod_security:
    jobs_level: maximum  # ValidationError: must be privileged, baseline, or restricted
```

## Backward Compatibility

### Minor Version Changes (Allowed)

- Adding new optional fields with defaults
- Adding new enum values (if consumers handle unknown values)

### Major Version Changes (Breaking)

- Removing fields
- Changing field types
- Making optional fields required
- Removing enum values

## Integration Points

### Consumers

1. **RBACManifestGenerator**: Reads SecurityConfig to determine what manifests to generate
2. **CompilationPipeline**: Validates SecurityConfig during Stage 3 (Validate)
3. **CLI**: `floe rbac generate` reads SecurityConfig from manifest.yaml

### Producers

1. **manifest.yaml**: Platform team writes security configuration
2. **Default values**: Applied by Pydantic when fields are omitted

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-19 | Initial schema definition |
