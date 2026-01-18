# floe-secrets-k8s

Kubernetes Secrets backend plugin for the floe data platform.

## Installation

```bash
pip install floe-secrets-k8s
```

## Usage

```python
from floe_secrets_k8s import K8sSecretsPlugin, K8sSecretsConfig

config = K8sSecretsConfig(namespace="floe-secrets")
plugin = K8sSecretsPlugin(config)
plugin.startup()

secret = plugin.get_secret("database-password")
plugin.shutdown()
```

## Features

- Namespace-scoped secret access
- In-cluster and kubeconfig authentication
- Pod spec generation for envFrom injection
- Structured audit logging

## License

Apache-2.0
