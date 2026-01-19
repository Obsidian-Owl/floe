# floe-rbac-k8s

Kubernetes RBAC plugin for the floe data platform.

## Overview

This plugin implements the `RBACPlugin` interface from floe-core, providing Kubernetes-native
RBAC manifest generation for:

- ServiceAccounts with least-privilege configurations
- Roles with constrained permissions (no wildcards)
- RoleBindings including cross-namespace access patterns
- Namespaces with Pod Security Standards labels

## Installation

```bash
pip install floe-rbac-k8s
```

## Usage

```python
from floe_rbac_k8s import K8sRBACPlugin
from floe_core.schemas.rbac import ServiceAccountConfig

plugin = K8sRBACPlugin()

# Generate a ServiceAccount manifest
config = ServiceAccountConfig(
    name="floe-job-runner",
    namespace="floe-jobs",
    automount_token=False
)
manifest = plugin.generate_service_account(config)
```

## Entry Point

This plugin registers under the `floe.rbac` entry point group:

```toml
[project.entry-points."floe.rbac"]
k8s = "floe_rbac_k8s:K8sRBACPlugin"
```

## Requirements

- Python 3.11+
- Kubernetes 1.28+ (for Pod Security Standards support)
- floe-core 0.1.0+

## License

Apache-2.0
