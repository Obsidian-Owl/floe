# Quickstart: Network and Pod Security (Epic 7C)

**Purpose**: Get developers started with the Network and Pod Security feature
**Prerequisite**: Epic 7B (K8s RBAC) complete - provides SecurityConfig foundation

## Overview

Epic 7C adds NetworkPolicy generation and Pod Security Standards enforcement to the floe platform. This builds on the existing `security` section in `manifest.yaml` by adding `network_policies` configuration.

## 1. Enable Network Policies

Add network policy configuration to your `manifest.yaml`:

```yaml
# manifest.yaml
version: "1.0"
name: my-platform

security:
  # Existing from Epic 7B
  rbac:
    enabled: true
    job_service_account: auto
  pod_security:
    jobs_level: restricted
    platform_level: baseline
  namespace_isolation: strict

  # NEW for Epic 7C
  network_policies:
    enabled: true
    default_deny: true
    allow_external_https: true
    ingress_controller_namespace: ingress-nginx
```

## 2. Generate NetworkPolicies

Run the compile command to generate NetworkPolicy manifests:

```bash
# Generate all artifacts including NetworkPolicies
floe compile

# Or generate only NetworkPolicies
floe network generate
```

Output will be in `target/network/`:
```
target/network/
├── floe-platform-default-deny.yaml
├── floe-platform-allow-ingress.yaml
├── floe-platform-allow-egress.yaml
├── floe-jobs-default-deny.yaml
├── floe-jobs-allow-egress.yaml
└── NETWORK-POLICY-SUMMARY.md
```

## 3. Review Generated Policies

Inspect the summary to understand what was generated:

```bash
cat target/network/NETWORK-POLICY-SUMMARY.md
```

Example summary:
```markdown
# NetworkPolicy Summary

## floe-jobs Namespace

### Default-Deny Egress
- Blocks all outbound traffic except explicitly allowed

### Allowed Egress
- DNS: UDP 53 → kube-system (required for service discovery)
- Polaris: TCP 8181 → floe-platform (catalog access)
- OTel: TCP 4317, 4318 → floe-platform (telemetry)
- MinIO: TCP 9000 → floe-platform (object storage)
- External HTTPS: TCP 443 → any (cloud DWH access)
```

## 4. Validate Before Deploying

Check that generated policies are valid and CNI supports them:

```bash
# Validate manifest syntax
floe network validate

# Check CNI plugin supports NetworkPolicies
floe network check-cni
```

## 5. Apply NetworkPolicies

```bash
# Apply all generated policies
kubectl apply -f target/network/

# Or apply per-namespace
kubectl apply -f target/network/floe-jobs-*.yaml
```

## 6. Verify Enforcement

Test that policies are working:

```bash
# From a job pod, this should succeed (allowed egress)
kubectl exec -n floe-jobs test-pod -- nslookup polaris.floe-platform

# From a job pod, this should fail (blocked)
kubectl exec -n floe-jobs test-pod -- curl http://arbitrary-service.other-namespace:8080
```

## 7. Adding Custom Egress Rules

Add custom egress allowlists for your specific needs:

```yaml
# manifest.yaml
security:
  network_policies:
    enabled: true
    jobs_egress_allow:
      - name: "snowflake-access"
        to_cidr: "0.0.0.0/0"
        port: 443
        protocol: TCP
    platform_egress_allow:
      - name: "vault-access"
        to_namespace: vault
        port: 8200
        protocol: TCP
```

## 8. Audit Deployed Policies

Check for drift between expected and deployed policies:

```bash
# Show current cluster NetworkPolicy state
floe network audit

# Show differences from expected state
floe network diff
```

## Common Tasks

### Disable NetworkPolicies (Development)

```yaml
security:
  network_policies:
    enabled: false  # Policies not generated
```

### Use Different Ingress Controller

```yaml
security:
  network_policies:
    ingress_controller_namespace: traefik  # Or any other
```

### Domain Namespace Isolation

Domain namespaces automatically get isolated policies:

```yaml
domains:
  - name: sales
    namespace: floe-sales-domain
  - name: marketing
    namespace: floe-marketing-domain
```

Each domain namespace will have:
- Default-deny ingress/egress
- Egress to shared platform services (Polaris, OTel)
- No cross-domain communication

## Troubleshooting

### Pods Can't Resolve DNS

DNS egress is always included. If DNS fails:
1. Check CNI supports NetworkPolicies: `floe network check-cni`
2. Verify kube-dns/coredns is in `kube-system` namespace
3. Check policy was applied: `kubectl get networkpolicy -n floe-jobs`

### Jobs Can't Reach External Services

1. Verify `allow_external_https: true` in config
2. Check egress allowlist includes the port: `cat target/network/floe-jobs-allow-egress.yaml`
3. For non-443 ports, add custom egress rule

### Platform Services Not Accessible

1. Verify ingress controller namespace is correct
2. Check ingress rules: `cat target/network/floe-platform-allow-ingress.yaml`
3. Verify service is exposed via Ingress resource

## Next Steps

- Read the [full spec](./spec.md) for all requirements
- Review [data model](./data-model.md) for schema details
- Check [contracts](./contracts/) for plugin interface details
