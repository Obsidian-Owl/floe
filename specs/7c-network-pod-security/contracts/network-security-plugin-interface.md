# Contract: NetworkSecurityPlugin Interface

**Version**: 1.0.0
**Epic**: 7C
**Date**: 2026-01-26

## Overview

The `NetworkSecurityPlugin` abstract base class defines the contract for generating Kubernetes NetworkPolicy and Pod Security resources.

## Plugin Metadata Contract

All implementations MUST inherit from `PluginMetadata` and provide:

```python
class NetworkSecurityPlugin(PluginMetadata):
    """Abstract base class for network security plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin identifier (e.g., 'k8s-network-security')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version (semver, e.g., '0.1.0')."""
        ...

    @property
    @abstractmethod
    def floe_api_version(self) -> str:
        """Minimum floe API version required (e.g., '1.0')."""
        ...
```

## Abstract Methods Contract

### generate_network_policy

```python
@abstractmethod
def generate_network_policy(
    self,
    config: NetworkPolicyConfig
) -> dict[str, Any]:
    """Generate a single K8s NetworkPolicy manifest.

    Args:
        config: NetworkPolicy configuration

    Returns:
        Dictionary representing K8s NetworkPolicy YAML

    Raises:
        ValidationError: If config is invalid
    """
    ...
```

**Output Contract**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: <config.name>
  namespace: <config.namespace>
  labels:
    app.kubernetes.io/managed-by: floe
    floe.dev/component: network-security
spec:
  podSelector: <config.pod_selector>
  policyTypes: <config.policy_types>
  ingress: <generated from config.ingress_rules>
  egress: <generated from config.egress_rules>
```

### generate_default_deny_policies

```python
@abstractmethod
def generate_default_deny_policies(
    self,
    namespace: str
) -> list[dict[str, Any]]:
    """Generate default-deny ingress and egress policies.

    Args:
        namespace: Target namespace

    Returns:
        List of NetworkPolicy manifests (ingress-deny, egress-deny)
    """
    ...
```

**Output Contract**:
Returns two policies:
1. `{namespace}-default-deny-ingress`: Denies all ingress
2. `{namespace}-default-deny-egress`: Denies all egress

### generate_dns_egress_rule

```python
@abstractmethod
def generate_dns_egress_rule(self) -> dict[str, Any]:
    """Generate DNS egress rule (always required).

    Returns:
        Egress rule allowing UDP 53 to kube-system
    """
    ...
```

**Output Contract**:
```yaml
to:
  - namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: kube-system
ports:
  - protocol: UDP
    port: 53
```

### generate_pod_security_context

```python
@abstractmethod
def generate_pod_security_context(
    self,
    config: PodSecurityContextConfig
) -> dict[str, Any]:
    """Generate pod-level securityContext.

    Args:
        config: Pod security context configuration

    Returns:
        Dictionary representing K8s pod securityContext
    """
    ...
```

**Output Contract**:
```yaml
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
fsGroup: 1000
seccompProfile:
  type: RuntimeDefault
```

### generate_container_security_context

```python
@abstractmethod
def generate_container_security_context(
    self,
    config: PodSecurityContextConfig
) -> dict[str, Any]:
    """Generate container-level securityContext.

    Args:
        config: Pod security context configuration

    Returns:
        Dictionary representing K8s container securityContext
    """
    ...
```

**Output Contract**:
```yaml
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop:
    - ALL
```

### generate_writable_volumes

```python
@abstractmethod
def generate_writable_volumes(
    self,
    writable_paths: list[str]
) -> tuple[list[dict], list[dict]]:
    """Generate emptyDir volumes for writable paths.

    Args:
        writable_paths: Paths needing write access (e.g., ["/tmp", "/home/floe"])

    Returns:
        Tuple of (volumes, volumeMounts)
    """
    ...
```

**Output Contract**:
```yaml
# volumes
- name: tmp-volume
  emptyDir: {}
- name: home-volume
  emptyDir: {}

# volumeMounts
- name: tmp-volume
  mountPath: /tmp
- name: home-volume
  mountPath: /home/floe
```

## Entry Point Registration

Implementations MUST register via entry points:

```toml
[project.entry-points."floe.network_security"]
k8s = "floe_network_security_k8s:K8sNetworkSecurityPlugin"
```

## Compliance Test Requirements

All implementations MUST pass `BaseNetworkSecurityPluginTests`:

1. `test_plugin_metadata` - name, version, floe_api_version present
2. `test_generate_network_policy_structure` - Valid K8s NetworkPolicy
3. `test_default_deny_blocks_all` - Empty rules = deny all
4. `test_dns_egress_always_present` - DNS rule never missing
5. `test_pod_security_context_restricted` - Meets restricted PSS
6. `test_container_security_context_hardened` - All capabilities dropped
7. `test_writable_volumes_emptydir` - Uses emptyDir (not hostPath)

## Version Compatibility

| Plugin API Version | floe-core Version | Changes |
|--------------------|-------------------|---------|
| 1.0 | 0.1.0+ | Initial release |

## Error Handling

All methods MUST raise `ValidationError` for invalid input rather than returning partial/invalid output.

```python
from pydantic import ValidationError

# Example
if not config.name.startswith("floe-"):
    raise ValidationError("NetworkPolicy name must start with 'floe-'")
```
