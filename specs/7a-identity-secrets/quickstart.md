# Quickstart: Epic 7A - Identity & Secrets Plugins

**Date**: 2026-01-18
**Status**: Draft
**Branch**: `7a-identity-secrets`

## Prerequisites

- Python 3.11+
- Kubernetes 1.28+ (Kind for local development)
- `uv` package manager installed
- floe-core package installed

## Quick Installation

```bash
# Install all identity and secrets plugins
uv pip install floe-secrets-k8s floe-secrets-infisical floe-identity-keycloak

# Or install individually
uv pip install floe-secrets-k8s        # K8s Secrets backend (default)
uv pip install floe-secrets-infisical  # Infisical backend (recommended OSS)
uv pip install floe-identity-keycloak  # Keycloak identity provider
```

## Basic Usage

### 1. K8s Secrets Plugin (Default)

```python
from floe_secrets_k8s import K8sSecretsPlugin, K8sSecretsConfig

# Initialize plugin with config (auto-detects in-cluster vs kubeconfig)
config = K8sSecretsConfig(namespace="floe-secrets")
plugin = K8sSecretsPlugin(config)

# Start the plugin (establishes K8s connection)
plugin.startup()

# Get a secret
password = plugin.get_secret("database-password")

# Set a secret
plugin.set_secret("api-key", "my-secret-value")

# List secrets
secrets = plugin.list_secrets(prefix="database-")

# Clean up when done
plugin.shutdown()
```

### 2. Infisical Secrets Plugin

```python
from floe_secrets_infisical import InfisicalSecretsPlugin, InfisicalSecretsConfig
from pydantic import SecretStr
import os

# Initialize with Universal Auth credentials via config
config = InfisicalSecretsConfig(
    client_id=os.environ["INFISICAL_CLIENT_ID"],
    client_secret=SecretStr(os.environ["INFISICAL_CLIENT_SECRET"]),
    project_id=os.environ["INFISICAL_PROJECT_ID"],
    environment="production",
)
plugin = InfisicalSecretsPlugin(config=config)

# Start the plugin (authenticates with Infisical)
plugin.startup()

# Use the same interface as K8s plugin
password = plugin.get_secret("database-password")

# Set a secret
plugin.set_secret("new-api-key", "secret-value")

# List secrets with prefix
secrets = plugin.list_secrets(prefix="database")

# Clean up when done
plugin.shutdown()
```

### 3. Keycloak Identity Plugin

```python
from floe_identity_keycloak import KeycloakIdentityPlugin, KeycloakIdentityConfig
from pydantic import SecretStr
import os

# Initialize with Keycloak configuration
config = KeycloakIdentityConfig(
    server_url="https://keycloak.example.com",
    realm="floe",
    client_id=os.environ["KEYCLOAK_CLIENT_ID"],
    client_secret=SecretStr(os.environ["KEYCLOAK_CLIENT_SECRET"]),
)
plugin = KeycloakIdentityPlugin(config)

# Start the plugin (fetches JWKS keys)
plugin.startup()

# Authenticate user (password grant)
token = plugin.authenticate({
    "username": "user@example.com",
    "password": os.environ["USER_PASSWORD"]
})

# Validate token
if token:
    result = plugin.validate_token(token)
    if result.valid:
        print(f"User: {result.user_info.email}")
        print(f"Roles: {result.user_info.roles}")

# Clean up when done
plugin.shutdown()
```

## Configuration in manifest.yaml

```yaml
# manifest.yaml
version: "1.0"
metadata:
  name: my-data-product
  domain: analytics

plugins:
  secrets:
    type: k8s  # or "infisical"
    config:
      namespace: floe-secrets

  identity:
    type: keycloak
    config:
      server_url: https://keycloak.example.com
      realm: floe
      client_id:
        secretRef:
          name: keycloak-credentials
          key: client-id
      client_secret:
        secretRef:
          name: keycloak-credentials
          key: client-secret
```

## Using SecretReference in floe.yaml

```yaml
# floe.yaml
pipelines:
  - name: load_snowflake
    source:
      type: snowflake
      credentials:
        account:
          secretRef:
            source: kubernetes
            name: snowflake-creds
            key: account
        username:
          secretRef:
            source: kubernetes
            name: snowflake-creds
            key: username
        password:
          secretRef:
            source: kubernetes
            name: snowflake-creds
            key: password
```

## Plugin Discovery

```python
from floe_core.plugins import get_registry

# List available secrets plugins
registry = get_registry()
secrets_plugins = registry.list_plugins("secrets")
print(secrets_plugins)  # ['k8s', 'infisical']

# Get a specific plugin
k8s_plugin = registry.get_plugin("secrets", "k8s")
```

## Testing Your Setup

```bash
# Run unit tests (no K8s required)
make test-unit

# Run integration tests (requires Kind cluster)
make test-k8s

# Verify plugin discovery
python -c "from floe_core.plugins import get_registry; print(get_registry().list_plugins('secrets'))"
```

## Environment Variables

### K8s Secrets Plugin
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| KUBECONFIG | No | ~/.kube/config | Path to kubeconfig (local dev) |

### Infisical Plugin
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| INFISICAL_CLIENT_ID | Yes | - | Universal Auth client ID |
| INFISICAL_CLIENT_SECRET | Yes | - | Universal Auth client secret |
| INFISICAL_PROJECT_ID | Yes | - | Infisical project ID |
| INFISICAL_SITE_URL | No | https://app.infisical.com | Self-hosted URL |

### Keycloak Plugin
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| KEYCLOAK_SERVER_URL | Yes | - | Keycloak server URL |
| KEYCLOAK_REALM | No | floe | Realm name |
| KEYCLOAK_CLIENT_ID | Yes | - | OIDC client ID |
| KEYCLOAK_CLIENT_SECRET | Yes | - | OIDC client secret |

## Audit Logging (FR-060)

All secrets plugins emit structured audit logs for compliance and security monitoring.
Logs are JSON-formatted via `structlog` and include OpenTelemetry trace context when available.

### Audit Event Schema

```json
{
  "timestamp": "2026-01-18T12:34:56.789Z",
  "requester_id": "dagster-worker-abc123",
  "secret_path": "database-password",
  "operation": "get",
  "result": "success",
  "plugin_type": "k8s",
  "namespace": "floe-secrets",
  "trace_id": "abc123def456789...",
  "span_id": "123456789...",
  "audit_event": true,
  "metadata": {
    "found": true
  }
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO8601 | Event timestamp (UTC) |
| `requester_id` | string | Identity performing the operation |
| `secret_path` | string | Secret key or path being accessed |
| `operation` | enum | `get`, `set`, `list`, `delete` |
| `result` | enum | `success`, `denied`, `error` |
| `plugin_type` | string | Plugin identifier (`k8s`, `infisical`) |
| `namespace` | string | K8s namespace or Infisical environment |
| `trace_id` | string | OpenTelemetry trace ID (if available) |
| `span_id` | string | OpenTelemetry span ID (if available) |
| `audit_event` | bool | Always `true` (for log filtering) |
| `metadata` | object | Operation-specific context |

### Operation-Specific Metadata

**GET operations**:
```json
{"found": true}           // Secret found and returned
{"found": false}          // Secret not found (returns None)
{"found": true, "multi_key": true, "key_count": 3}  // get_multi_key_secret
```

**SET operations**:
```json
{"action": "created"}     // New secret created
{"action": "updated"}     // Existing secret updated
```

**LIST operations**:
```json
{"count": 15}             // Number of secrets matching prefix
```

**DELETE operations** (Infisical only):
```json
{"path": "/secrets/db"}   // Path where secret was deleted
```

### Log Levels by Result

| Result | Log Level | When |
|--------|-----------|------|
| `success` | INFO | Successful operation |
| `denied` | WARNING | Access denied (403) |
| `error` | ERROR | Backend unavailable, timeout, etc. |

### Querying Audit Logs

**Filter by audit events only**:
```bash
# Using jq to filter structured logs
cat logs.json | jq 'select(.audit_event == true)'

# Filter for denied access attempts
cat logs.json | jq 'select(.audit_event == true and .result == "denied")'

# Filter by secret path
cat logs.json | jq 'select(.audit_event == true and .secret_path | contains("database"))'
```

**Example: Find all denied access in last hour**:
```bash
cat logs.json | jq --arg since "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  'select(.audit_event == true and .result == "denied" and .timestamp > $since)'
```

### Configuring Log Output

Audit logs use Python's `structlog` with JSON output. Configure via standard logging:

```python
import structlog
import logging

# Configure structlog for JSON output
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# Set log level for audit logger
logging.getLogger("floe.audit").setLevel(logging.INFO)
```

### OpenTelemetry Integration

When OpenTelemetry is configured, audit events automatically include trace context:

```python
from opentelemetry import trace

tracer = trace.get_tracer("my-service")

with tracer.start_as_current_span("get_credentials"):
    # Audit log will include trace_id and span_id
    secret = plugin.get_secret("db-password")
```

This enables correlating audit events with distributed traces in tools like Jaeger.

## InfisicalSecret CRD Integration (FR-022, FR-023)

The Infisical Kubernetes Operator enables automatic synchronization of secrets
from Infisical to Kubernetes Secrets, with auto-reload capabilities.

### Prerequisites

1. **Install Infisical Operator**:
```bash
# Add Infisical Helm repository
helm repo add infisical https://dl.cloudsmith.io/public/infisical/helm-charts/helm/charts/
helm repo update

# Install the operator
helm install infisical-secrets-operator infisical/secrets-operator \
  --namespace infisical-operator \
  --create-namespace
```

2. **Create Universal Auth credentials**:
   - Create a Machine Identity in Infisical with Universal Auth
   - Store credentials in a K8s Secret for the operator

### Creating InfisicalSecret CRD

```yaml
# infisical-secret.yaml
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: snowflake-credentials
  namespace: floe-jobs
  annotations:
    # Enable auto-reload of pods when secret changes (FR-023)
    secrets.infisical.com/auto-reload: "true"
spec:
  # Infisical API endpoint (cloud or self-hosted)
  hostAPI: https://app.infisical.com

  # How often to sync (default: 1m)
  resyncInterval: 60

  # Authentication configuration
  authentication:
    universalAuth:
      # Reference to K8s secret with credentials
      credentialsRef:
        secretName: infisical-credentials
        secretNamespace: floe-jobs
      # Scope for secrets
      secretsScope:
        projectSlug: my-project
        envSlug: production
        secretsPath: /compute/snowflake

  # Managed K8s Secret configuration
  managedSecretReference:
    secretName: synced-snowflake-creds
    secretNamespace: floe-jobs
    secretType: Opaque
```

### Creating Operator Credentials Secret

```yaml
# infisical-credentials.yaml
apiVersion: v1
kind: Secret
metadata:
  name: infisical-credentials
  namespace: floe-jobs
type: Opaque
stringData:
  clientId: "your-universal-auth-client-id"
  clientSecret: "your-universal-auth-client-secret"
```

Apply both:
```bash
kubectl apply -f infisical-credentials.yaml
kubectl apply -f infisical-secret.yaml
```

### Auto-Reload Configuration (FR-023)

To automatically restart pods when secrets change, add this annotation to your Deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: floe-worker
  namespace: floe-jobs
spec:
  template:
    metadata:
      annotations:
        # Watches the InfisicalSecret for changes
        secrets.infisical.com/auto-reload: "true"
    spec:
      containers:
        - name: worker
          env:
            - name: SNOWFLAKE_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: synced-snowflake-creds
                  key: password
```

### Using in manifest.yaml

```yaml
# manifest.yaml
version: "1.0"
metadata:
  name: my-data-product
  domain: analytics

plugins:
  secrets:
    type: infisical
    config:
      client_id:
        secretRef:
          name: infisical-credentials
          key: clientId
      client_secret:
        secretRef:
          name: infisical-credentials
          key: clientSecret
      project_id: "proj_12345"
      environment: production
      secret_path: /compute/snowflake
```

### Verifying Sync

```bash
# Check InfisicalSecret status
kubectl get infisicalsecret snowflake-credentials -n floe-jobs -o yaml

# Verify K8s secret was created
kubectl get secret synced-snowflake-creds -n floe-jobs

# View synced secret keys (don't show values!)
kubectl get secret synced-snowflake-creds -n floe-jobs -o jsonpath='{.data}' | jq 'keys'
```

### Troubleshooting InfisicalSecret

**"Secret not syncing"**:
```bash
# Check operator logs
kubectl logs -n infisical-operator -l app=infisical-secrets-operator

# Check InfisicalSecret status conditions
kubectl describe infisicalsecret snowflake-credentials -n floe-jobs
```

**"Authentication failed"**:
```bash
# Verify credentials secret exists
kubectl get secret infisical-credentials -n floe-jobs

# Check if client_id and clientSecret keys exist
kubectl get secret infisical-credentials -n floe-jobs -o jsonpath='{.data}' | jq 'keys'
```

## Next Steps

1. **Deploy Keycloak**: See `charts/keycloak/` for Helm deployment
2. **Configure Infisical Operator**: See ADR-0031 for K8s integration
3. **Set up RBAC**: Configure K8s ServiceAccount permissions for secrets access

## Troubleshooting

### "Permission denied reading secret"
```bash
# Check ServiceAccount RBAC
kubectl auth can-i get secrets --as=system:serviceaccount:floe:floe-worker -n floe-secrets
```

### "Connection refused to Keycloak"
```bash
# Verify Keycloak is accessible
curl -s https://keycloak.example.com/realms/floe/.well-known/openid-configuration | jq .
```

### "Infisical authentication failed"
```bash
# Test Universal Auth credentials
curl -X POST https://app.infisical.com/api/v1/auth/universal-auth/login \
  -H "Content-Type: application/json" \
  -d '{"clientId": "...", "clientSecret": "..."}'
```
