# Quickstart: K8s RBAC Plugin System

**Feature**: Epic 7B - K8s RBAC Plugin System
**Date**: 2026-01-19

## Prerequisites

- Kubernetes 1.28+ cluster with Pod Security Admission enabled
- floe-core installed with Epic 7A (Identity & Secrets) complete
- `kubectl` configured with cluster access
- Python 3.11+

## Installation

```bash
# Install floe-core (includes RBACPlugin ABC)
pip install floe-core

# Install K8s RBAC plugin implementation
pip install floe-rbac-k8s
```

## Basic Usage

### 1. Configure Security in manifest.yaml

```yaml
# manifest.yaml
version: "1.0"
name: my-data-platform

security:
  rbac:
    enabled: true
    job_service_account: auto
  pod_security:
    jobs_level: restricted
    platform_level: baseline
  namespace_isolation: strict
```

### 2. Generate RBAC Manifests

```bash
# Generate RBAC manifests during compilation
floe compile

# Or generate RBAC manifests only
floe rbac generate

# Output directory structure:
# target/rbac/
#   ├── namespaces.yaml
#   ├── serviceaccounts.yaml
#   ├── roles.yaml
#   └── rolebindings.yaml
```

### 3. Apply to Kubernetes

```bash
# Validate manifests first (dry-run)
kubectl apply --dry-run=server -f target/rbac/

# Apply manifests
kubectl apply -f target/rbac/
```

### 4. Verify Deployment

```bash
# Check namespaces with PSS labels
kubectl get ns -l app.kubernetes.io/managed-by=floe

# Check service accounts
kubectl get sa -n floe-jobs -l app.kubernetes.io/managed-by=floe

# Check roles and bindings
kubectl get roles,rolebindings -n floe-jobs -l app.kubernetes.io/managed-by=floe
```

## Common Scenarios

### Scenario 1: Data Job with Secret Access

```yaml
# floe.yaml
data_products:
  - name: customer-analytics
    compute:
      credentials_ref: snowflake-creds  # Secret name

# Generated Role (target/rbac/roles.yaml)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: floe-job-runner-role
  namespace: floe-jobs
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get"]
    resourceNames: ["snowflake-creds"]
```

### Scenario 2: Cross-Namespace Access for Dagster

```yaml
# manifest.yaml
security:
  rbac:
    enabled: true

# Dagster in floe-platform can create jobs in floe-jobs
# Generated RoleBinding allows cross-namespace access
```

### Scenario 3: Custom Pod Security Level

```yaml
# manifest.yaml
security:
  pod_security:
    jobs_level: baseline  # Less restrictive for specific workloads
    platform_level: baseline
```

## CLI Commands

```bash
# Generate RBAC manifests
floe rbac generate

# Validate generated manifests against config
floe rbac validate

# Audit current cluster RBAC state
floe rbac audit

# Show differences between expected and deployed RBAC
floe rbac diff
```

## Troubleshooting

### Issue: Pod fails to start with permission denied

```bash
# Check if ServiceAccount exists
kubectl get sa floe-job-runner -n floe-jobs

# Check RoleBinding
kubectl get rolebinding -n floe-jobs -o yaml

# Verify secret access
kubectl auth can-i get secrets/snowflake-creds \
  --as=system:serviceaccount:floe-jobs:floe-job-runner \
  -n floe-jobs
```

### Issue: Pod rejected by Pod Security Admission

```bash
# Check namespace PSS labels
kubectl get ns floe-jobs -o yaml | grep pod-security

# Check pod securityContext
kubectl get pod <pod-name> -n floe-jobs -o yaml | grep -A20 securityContext
```

### Issue: RBAC manifests not generated

```bash
# Verify security.rbac.enabled in manifest.yaml
floe config show | grep -A5 security

# Check compilation output
floe compile --verbose
```

## Next Steps

- Configure domain namespaces for multi-tenant deployments
- Set up RBAC audit logging
- Integrate with CI/CD for automated RBAC deployment
- Review ADR-0022 for advanced security patterns
