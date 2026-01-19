# Contract: Dagster Helm Values Schema

**Version**: 1.0.0
**Status**: Draft

## Overview

This contract defines the structure of Helm values returned by
`DagsterOrchestratorPlugin.get_helm_values()`.

## Schema Definition

```yaml
# Top-level structure returned by get_helm_values()
dagster-webserver:
  enabled: true
  replicaCount: 1
  resources:
    requests:
      cpu: "100m"
      memory: "256Mi"
    limits:
      cpu: "500m"
      memory: "512Mi"

dagster-daemon:
  enabled: true
  replicaCount: 1
  resources:
    requests:
      cpu: "100m"
      memory: "256Mi"
    limits:
      cpu: "500m"
      memory: "512Mi"

dagster-user-code:
  enabled: true
  replicaCount: 1
  resources:
    requests:
      cpu: "250m"
      memory: "512Mi"
    limits:
      cpu: "1000m"
      memory: "1Gi"

postgresql:
  enabled: true  # Use embedded PostgreSQL
  # OR external connection:
  # enabled: false
  # externalDatabase:
  #   host: "postgres.example.com"
  #   port: 5432
```

## Resource Presets

### Small (Development)

```yaml
dagster-webserver:
  resources:
    requests: {cpu: "100m", memory: "256Mi"}
    limits: {cpu: "500m", memory: "512Mi"}
dagster-daemon:
  resources:
    requests: {cpu: "100m", memory: "256Mi"}
    limits: {cpu: "500m", memory: "512Mi"}
dagster-user-code:
  resources:
    requests: {cpu: "250m", memory: "512Mi"}
    limits: {cpu: "1000m", memory: "1Gi"}
```

### Medium (Staging)

```yaml
dagster-webserver:
  resources:
    requests: {cpu: "250m", memory: "512Mi"}
    limits: {cpu: "1000m", memory: "1Gi"}
dagster-daemon:
  resources:
    requests: {cpu: "250m", memory: "512Mi"}
    limits: {cpu: "1000m", memory: "1Gi"}
dagster-user-code:
  resources:
    requests: {cpu: "500m", memory: "1Gi"}
    limits: {cpu: "2000m", memory: "4Gi"}
```

### Large (Production)

```yaml
dagster-webserver:
  resources:
    requests: {cpu: "500m", memory: "1Gi"}
    limits: {cpu: "2000m", memory: "2Gi"}
dagster-daemon:
  resources:
    requests: {cpu: "500m", memory: "1Gi"}
    limits: {cpu: "2000m", memory: "2Gi"}
dagster-user-code:
  resources:
    requests: {cpu: "1000m", memory: "2Gi"}
    limits: {cpu: "4000m", memory: "8Gi"}
```

## JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "dagster-webserver": {
      "type": "object",
      "properties": {
        "enabled": {"type": "boolean", "default": true},
        "replicaCount": {"type": "integer", "minimum": 1},
        "resources": {"$ref": "#/definitions/resources"}
      }
    },
    "dagster-daemon": {
      "type": "object",
      "properties": {
        "enabled": {"type": "boolean", "default": true},
        "replicaCount": {"type": "integer", "minimum": 1},
        "resources": {"$ref": "#/definitions/resources"}
      }
    },
    "dagster-user-code": {
      "type": "object",
      "properties": {
        "enabled": {"type": "boolean", "default": true},
        "replicaCount": {"type": "integer", "minimum": 1},
        "resources": {"$ref": "#/definitions/resources"}
      }
    },
    "postgresql": {
      "type": "object",
      "properties": {
        "enabled": {"type": "boolean"}
      }
    }
  },
  "definitions": {
    "resources": {
      "type": "object",
      "properties": {
        "requests": {
          "type": "object",
          "properties": {
            "cpu": {"type": "string"},
            "memory": {"type": "string"}
          }
        },
        "limits": {
          "type": "object",
          "properties": {
            "cpu": {"type": "string"},
            "memory": {"type": "string"}
          }
        }
      }
    }
  }
}
```

## Validation

Helm values are validated by:
1. `helm lint` against floe-dagster chart
2. Unit tests in `test_helm_values.py`
3. Integration tests with real Helm deployment
