# floe-network-security-k8s

Kubernetes Network Security plugin for the floe data platform.

## Overview

This plugin implements the `NetworkSecurityPlugin` interface from floe-core, providing
Kubernetes-native NetworkPolicy and Pod Security manifest generation for:

- Default-deny NetworkPolicies for job and platform namespaces
- Egress allowlists for DNS, catalog, telemetry, and storage services
- Ingress rules for ingress controller and intra-namespace communication
- Pod Security Standards namespace labels (restricted/baseline)
- Hardened container securityContext configurations

## Installation

```bash
pip install floe-network-security-k8s
```

## Usage

```python
from floe_network_security_k8s import K8sNetworkSecurityPlugin
from floe_core.network import NetworkPolicyConfig

plugin = K8sNetworkSecurityPlugin()

# Generate default-deny policies for a namespace
policies = plugin.generate_default_deny_policies("floe-jobs")

# Generate DNS egress rule (always required)
dns_rule = plugin.generate_dns_egress_rule()
```

## Entry Point

This plugin registers under the `floe.network_security` entry point group:

```toml
[project.entry-points."floe.network_security"]
k8s = "floe_network_security_k8s:K8sNetworkSecurityPlugin"
```

## Requirements

- Python 3.10+
- Kubernetes 1.25+ (for Pod Security Admission controller)
- CNI with NetworkPolicy support (Calico, Cilium, or cloud-native CNI)
- floe-core 0.1.0+

## Features

### NetworkPolicy Generation

- Default-deny ingress and egress policies
- DNS egress always allowed (UDP 53 to kube-system)
- Platform service egress (Polaris, OTel Collector, MinIO)
- External HTTPS egress (configurable)
- Custom egress rules via manifest.yaml

### Pod Security Standards

- Namespace labels for PSS enforcement
- Restricted level for job pods
- Baseline level for platform services
- Audit and warn labels for visibility

### Container Hardening

- `runAsNonRoot: true`
- `readOnlyRootFilesystem: true`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: ["ALL"]`
- `seccompProfile: RuntimeDefault`

## License

Apache-2.0
