# Data Model: Epic 9B - Helm Charts and Kubernetes Deployment

**Date**: 2026-02-01
**Epic**: 9B

## Overview

This document defines the key entities, their relationships, and validation rules for Epic 9B. These entities represent both Helm chart structure and runtime deployment state.

---

## 1. Core Entities

### FloeHelmChart

Represents a Helm chart in the floe ecosystem.

```yaml
entity: FloeHelmChart
description: Metadata for a floe Helm chart
fields:
  - name: name
    type: string
    required: true
    validation: "^[a-z][a-z0-9-]*$"
    description: Chart name (e.g., "floe-platform", "floe-jobs")

  - name: version
    type: string
    required: true
    validation: "^\\d+\\.\\d+\\.\\d+(-[a-z0-9.]+)?$"
    description: Semantic version of the chart

  - name: appVersion
    type: string
    required: true
    description: Version of the application being deployed

  - name: dependencies
    type: list[ChartDependency]
    required: false
    description: Subchart dependencies

  - name: valuesSchema
    type: JSONSchema
    required: true
    description: JSON Schema for values.yaml validation

  - name: compatibilityMatrix
    type: dict[string, string]
    required: true
    description: Mapping of chart version to compatible floe-core versions
```

### ChartDependency

```yaml
entity: ChartDependency
description: A subchart dependency declaration
fields:
  - name: name
    type: string
    required: true
    description: Dependency chart name

  - name: version
    type: string
    required: true
    description: Version constraint (exact or range)

  - name: repository
    type: string
    required: true
    validation: "^(https?://|oci://|file://)"
    description: Helm repository URL

  - name: condition
    type: string
    required: false
    description: values.yaml path to enable/disable (e.g., "dagster.enabled")

  - name: alias
    type: string
    required: false
    description: Override name for subchart values
```

---

### ClusterMapping

Represents the mapping from logical environments to physical clusters.

```yaml
entity: ClusterMapping
description: Logical-to-physical environment mapping
fields:
  - name: name
    type: string
    required: true
    description: Mapping identifier (e.g., "non-prod", "prod")

  - name: cluster
    type: string
    required: true
    description: Kubernetes cluster context or ArgoCD destination

  - name: environments
    type: list[string]
    required: true
    validation: "len >= 1"
    description: Logical environments mapped to this cluster

  - name: namespaceTemplate
    type: string
    required: true
    default: "floe-{{.environment}}"
    description: Go template for namespace naming

  - name: isolation
    type: enum[namespace, label]
    required: true
    default: namespace
    description: How environments are isolated within cluster

  - name: resources
    type: ResourcePreset
    required: true
    description: Resource allocation preset for this mapping
```

### ResourcePreset

```yaml
entity: ResourcePreset
description: Predefined resource allocation tier
fields:
  - name: name
    type: enum[small, medium, large, custom]
    required: true
    description: Preset tier name

  - name: webserver
    type: ResourceRequirements
    required: true
    description: Resources for webserver pods

  - name: daemon
    type: ResourceRequirements
    required: true
    description: Resources for daemon pods

  - name: userCode
    type: ResourceRequirements
    required: true
    description: Resources for user code pods

  - name: jobs
    type: ResourceRequirements
    required: true
    description: Resources for job pods
```

### ResourceRequirements

```yaml
entity: ResourceRequirements
description: Kubernetes resource requests and limits
fields:
  - name: requests
    type: ResourceSpec
    required: true
    description: Minimum guaranteed resources

  - name: limits
    type: ResourceSpec
    required: true
    description: Maximum allowed resources

nested:
  ResourceSpec:
    fields:
      - name: cpu
        type: string
        required: true
        validation: "^\\d+m?$"
        description: CPU in cores or millicores

      - name: memory
        type: string
        required: true
        validation: "^\\d+(Mi|Gi)$"
        description: Memory with unit suffix
```

---

### HelmValuesGenerator

Represents the service that generates Helm values from CompiledArtifacts.

```yaml
entity: HelmValuesGenerator
description: Generates values.yaml from CompiledArtifacts
fields:
  - name: artifacts
    type: CompiledArtifacts
    required: true
    description: Source artifacts for value generation

  - name: environment
    type: string
    required: true
    description: Target environment for generation

  - name: chartDefaults
    type: dict[string, Any]
    required: true
    description: Base values from chart values.yaml

  - name: pluginValues
    type: dict[string, Any]
    computed: true
    description: Merged values from plugin.get_helm_values()

methods:
  - name: generate
    returns: dict[string, Any]
    description: Produce merged values for Helm installation

  - name: validate
    returns: list[ValidationError]
    description: Validate generated values against schema
```

---

### PlatformDeployment

Represents a deployed instance of the floe platform.

```yaml
entity: PlatformDeployment
description: Deployed platform instance with status tracking
fields:
  - name: releaseName
    type: string
    required: true
    description: Helm release name

  - name: namespace
    type: string
    required: true
    description: Kubernetes namespace

  - name: chartVersion
    type: string
    required: true
    description: Deployed chart version

  - name: artifactVersion
    type: string
    required: true
    description: CompiledArtifacts version used

  - name: environment
    type: string
    required: true
    description: Logical environment

  - name: status
    type: enum[pending, deployed, failed, superseded]
    required: true
    description: Helm release status

  - name: components
    type: list[DeployedComponent]
    required: true
    description: Status of individual platform components

  - name: deployedAt
    type: datetime
    required: true
    description: Deployment timestamp

  - name: deployedBy
    type: string
    required: false
    description: User or system that initiated deployment
```

### DeployedComponent

```yaml
entity: DeployedComponent
description: Status of a deployed platform component
fields:
  - name: name
    type: string
    required: true
    description: Component name (e.g., "dagster-webserver", "polaris")

  - name: type
    type: enum[Deployment, StatefulSet, DaemonSet, Job, CronJob]
    required: true
    description: Kubernetes workload type

  - name: replicas
    type: object
    required: true
    properties:
      desired: integer
      ready: integer
      available: integer

  - name: health
    type: enum[healthy, degraded, unhealthy, unknown]
    required: true
    description: Component health based on probes
```

---

### DataProductJob

Represents a Kubernetes Job for dbt/data product execution.

```yaml
entity: DataProductJob
description: K8s Job for dbt execution with lifecycle management
fields:
  - name: name
    type: string
    required: true
    validation: "^[a-z][a-z0-9-]*$"
    description: Job name (derived from dbt model)

  - name: namespace
    type: string
    required: true
    description: Target namespace

  - name: image
    type: string
    required: true
    description: Container image for dbt execution

  - name: command
    type: list[string]
    required: true
    description: dbt command to execute

  - name: artifacts
    type: ConfigMapRef
    required: true
    description: Reference to CompiledArtifacts ConfigMap

  - name: secrets
    type: list[SecretRef]
    required: true
    description: References to credential secrets

  - name: resources
    type: ResourceRequirements
    required: true
    description: Job resource limits

  - name: status
    type: JobStatus
    computed: true
    description: Current job execution status

nested:
  JobStatus:
    fields:
      - name: phase
        type: enum[Pending, Running, Succeeded, Failed]
      - name: startTime
        type: datetime
      - name: completionTime
        type: datetime
      - name: logs
        type: string
        description: Container logs (on failure)
```

---

## 2. Entity Relationships

```
FloeHelmChart
  ├── 1:N → ChartDependency (dependencies)
  └── 1:1 → JSONSchema (valuesSchema)

ClusterMapping
  ├── 1:N → string (environments)
  └── 1:1 → ResourcePreset (resources)

HelmValuesGenerator
  ├── 1:1 → CompiledArtifacts (input)
  └── 1:1 → dict (output values)

PlatformDeployment
  ├── 1:N → DeployedComponent (components)
  └── 1:1 → ClusterMapping (via environment)

DataProductJob
  ├── 1:1 → ConfigMapRef (artifacts)
  └── 1:N → SecretRef (secrets)
```

---

## 3. Validation Rules

### Chart Naming

- Chart name MUST match regex `^[a-z][a-z0-9-]*$`
- Chart version MUST be valid semver
- Dependencies MUST specify exact or range versions

### Cluster Mapping

- Each environment MUST appear in exactly one cluster mapping
- Namespace template MUST produce valid K8s namespace names
- At least one environment MUST be defined per mapping

### Resource Presets

| Preset | webserver | daemon | userCode | jobs |
|--------|-----------|--------|----------|------|
| small | 100m/256Mi | 100m/256Mi | 250m/512Mi | 100m/256Mi |
| medium | 250m/512Mi | 250m/512Mi | 500m/1Gi | 250m/512Mi |
| large | 500m/1Gi | 500m/1Gi | 1000m/2Gi | 500m/1Gi |

### Generated Values

- Generated values MUST pass JSON Schema validation
- Secret references MUST NOT contain actual credentials
- All required values MUST be present before deployment

---

## 4. State Transitions

### PlatformDeployment.status

```
[Initial] --> pending --> deployed
                     \--> failed
deployed --> superseded (on upgrade)
failed --> pending (on retry)
```

### DataProductJob.status.phase

```
[Created] --> Pending --> Running --> Succeeded
                     \--> Failed
```

---

## 5. Integration with CompiledArtifacts

The `HelmValuesGenerator` consumes `CompiledArtifacts` to produce Helm values:

| CompiledArtifacts Field | Helm Values Mapping |
|-------------------------|---------------------|
| `plugins.orchestrator` | `dagster.*` section |
| `plugins.catalog` | `polaris.*` section |
| `plugins.telemetry_backend` | `otel.exporters.*` |
| `plugins.lineage_backend` | `marquez.*` section |
| `observability.telemetry` | `otel.config.*` |
| `transforms.models` | Job ConfigMap data |
| `dbt_profiles` | Job volume mount |

---

## 6. Pydantic Models

These entities will be implemented as Pydantic v2 models in `packages/floe-core/src/floe_core/helm/`:

```python
from pydantic import BaseModel, ConfigDict, Field

class ResourceSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    cpu: str = Field(pattern=r"^\d+m?$")
    memory: str = Field(pattern=r"^\d+(Mi|Gi)$")

class ResourceRequirements(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    requests: ResourceSpec
    limits: ResourceSpec

class ClusterMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    cluster: str
    environments: list[str] = Field(min_length=1)
    namespace_template: str = "floe-{{.environment}}"
    isolation: Literal["namespace", "label"] = "namespace"
```
