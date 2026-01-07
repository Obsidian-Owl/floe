# REQ-621 to REQ-635: Helm Chart Architecture

**Domain**: Deployment and Operations
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines Helm chart structure, configuration management, and deployment patterns for floe. Helm charts provide versioned, repeatable deployments across dev/staging/production environments.

**Key Principle**: Infrastructure as code (ADR-0019)

## Requirements

### REQ-621: Main Platform Chart Structure **[New]**

**Requirement**: System MUST provide main Helm chart `charts/floe-platform/` that deploys complete platform stack as a single unit.

**Rationale**: Enables one-command deployment of entire platform.

**Acceptance Criteria**:
- [ ] Chart: `charts/floe-platform/`
- [ ] Chart.yaml: name, version, appVersion, description
- [ ] values.yaml: environment-specific overrides
- [ ] templates/: Kubernetes resource templates for all services
- [ ] Chart includes subcharts: otel-collector, floe-services (optional)
- [ ] Helm lint passes without warnings
- [ ] Chart publishes to OCI registry (OCI-based Helm distribution)

**Enforcement**:
- Helm lint tests (chart syntax validation)
- Chart deployment tests (helm install succeeds)
- Chart upgrade tests (helm upgrade without downtime)

**Constraints**:
- MUST use Helm 3+
- MUST follow Helm best practices (metadata, conditions, etc.)
- MUST NOT hardcode environment-specific values
- FORBIDDEN to use deprecated Helm APIs

**Test Coverage**: `tests/integration/test_helm_platform_chart.py`

**Traceability**:
- ADR-0019 (Platform Services Lifecycle)
- Helm Chart Best Practices documentation

---

### REQ-622: Environment-Specific Values **[New]**

**Requirement**: System MUST provide environment-specific values.yaml files (dev, staging, prod) with overrides for scaling, resource limits, and backend configuration.

**Rationale**: Enables same Helm chart across all environments with environment-specific configuration.

**Acceptance Criteria**:
- [ ] values-dev.yaml: development defaults (1 replica, smaller resources)
- [ ] values-staging.yaml: staging configuration (2+ replicas, moderate resources)
- [ ] values-prod.yaml: production configuration (HA, large resources, external backends)
- [ ] Base values.yaml: common configuration (shared across all environments)
- [ ] Override mechanism: helm install -f values-dev.yaml (standard Helm pattern)
- [ ] Variable interpolation in templates: {{ .Values.replicaCount }} etc.

**Enforcement**:
- values.yaml schema validation (required fields present)
- Environment deployment tests (deploy with each values file)
- Configuration verification tests (correct values applied)

**Constraints**:
- MUST use standard Helm values file naming
- MUST NOT hardcode values in templates
- MUST document all configurable values in README
- FORBIDDEN to use environment variables for static configuration (use values.yaml)

**Test Coverage**: `tests/integration/test_helm_values_override.py`

**Traceability**:
- Helm Values documentation
- TESTING.md (environment configuration)

---

### REQ-623: Service Dependencies and Chart Ordering **[New]**

**Requirement**: System MUST manage service startup order and dependencies via Helm init containers, wait functions, and probes.

**Rationale**: Ensures services start in correct order (database before application).

**Acceptance Criteria**:
- [ ] PostgreSQL StatefulSet starts before dependent services (ordering via deployment strategy)
- [ ] Init containers wait for dependencies (e.g., wait-for-postgres.sh)
- [ ] Readiness probes block traffic until dependencies available
- [ ] Service-to-service dependencies documented (e.g., Dagster → PostgreSQL)
- [ ] Helm values control wait timeouts (configurable)
- [ ] Startup failures logged with clear error messages

**Enforcement**:
- Dependency ordering tests (pods start in correct order)
- Init container validation (wait logic works)
- Integration tests (all services healthy after deployment)

**Constraints**:
- MUST use Helm hooks or init containers for ordering (not shell scripts)
- MUST set reasonable wait timeouts (not infinite)
- MUST fail fast on dependency timeout (clear error)
- FORBIDDEN to rely on timing delays (use proper wait logic)

**Test Coverage**: `tests/integration/test_helm_service_ordering.py`

**Traceability**:
- Helm Hooks documentation
- REQ-611 (Init Containers)

---

### REQ-624: Configuration Management (ConfigMap and Secrets) **[New]**

**Requirement**: System MUST manage configuration via Helm ConfigMaps and Kubernetes Secrets.

**Rationale**: Enables dynamic configuration updates without image changes.

**Acceptance Criteria**:
- [ ] ConfigMap: OTLP Collector configuration (collector-config.yaml)
- [ ] ConfigMap: dbt project configuration (dbt_project.yml template)
- [ ] Secret: database passwords (generated or injected)
- [ ] Secret: API keys (sourced from environment)
- [ ] ConfigMap changes trigger pod restart (via annotation hash)
- [ ] Secret rotation supported (external secret managers)

**Enforcement**:
- ConfigMap creation and validation tests
- Secret creation tests (verify RBAC)
- Configuration reload tests (config changes reflected in pods)
- Sensitive data in ConfigMap detection tests (should fail)

**Constraints**:
- MUST use ConfigMap only for non-sensitive configuration
- MUST use Secrets for passwords, keys, and credentials
- MUST NOT commit Secrets to git
- FORBIDDEN to use files in images for configuration (use Helm values)

**Test Coverage**: `tests/integration/test_helm_configmaps_secrets.py`

**Traceability**:
- Kubernetes ConfigMap documentation
- Kubernetes Secrets documentation
- REQ-614 (Secret Management)

---

### REQ-625: Helm Chart Dependencies (Subcharts) **[New]**

**Requirement**: System MUST manage Helm chart dependencies via Chart.yaml and Helm repositories.

**Rationale**: Enables composition of reusable charts (PostgreSQL, Redis, etc.).

**Acceptance Criteria**:
- [ ] Chart.yaml declares dependencies (floe-platform depends on otel-collector, floe-services)
- [ ] Subchart overrides via parent values.yaml
- [ ] Dependency locking via Chart.lock (helm dependency update)
- [ ] Example: floe-platform → (otel-collector, floe-services)
- [ ] Helm dependency resolution: parent → subcharts → repositories
- [ ] Charts in public Helm repositories (e.g., Bitnami PostgreSQL)

**Enforcement**:
- Chart.yaml dependency validation
- Dependency resolution tests (helm dependency list)
- Subchart override validation

**Constraints**:
- MUST use Chart.yaml for dependencies (not manual installation)
- MUST pin dependency versions (not floating versions)
- MUST resolve dependencies before deployment (helm dependency update)
- FORBIDDEN to embed dependency charts in repository (use repositories)

**Test Coverage**: `tests/integration/test_helm_dependencies.py`

**Traceability**:
- Helm Chart Dependencies documentation
- Helm Repositories documentation

---

### REQ-626: OTLP Collector Chart **[New]**

**Requirement**: System MUST provide dedicated Helm chart `charts/otel-collector/` for deploying OpenTelemetry Collector.

**Rationale**: Enables consistent observability infrastructure deployment.

**Acceptance Criteria**:
- [ ] Chart: `charts/otel-collector/`
- [ ] Deployment: OTLP Collector (multiple replicas)
- [ ] Service: OTLP gRPC (port 4317), OTLP HTTP (port 4318)
- [ ] ConfigMap: collector configuration (pipeline, processors)
- [ ] Configurable backend exporters: Jaeger, Datadog, Grafana Cloud
- [ ] Values control: sampling rate, batch size, timeout
- [ ] Prometheus metrics endpoint (optional)

**Enforcement**:
- Chart deployment tests (collector starts and ready)
- OTLP endpoint tests (gRPC and HTTP receivers working)
- Exporter configuration tests (backend-specific config applied)

**Constraints**:
- MUST use official OpenTelemetry Collector image
- MUST support configurable backends via values.yaml
- MUST expose OTLP receivers on standard ports
- FORBIDDEN to hardcode collector configuration in chart

**Test Coverage**: `tests/integration/test_helm_otel_collector.py`

**Traceability**:
- REQ-507 (OTLP Collector Integration)
- OpenTelemetry Collector Helm charts documentation

---

### REQ-627: Job Template Chart **[New]**

**Requirement**: System MUST provide base Helm chart `charts/floe-jobs/` for templating Layer 4 (job) deployments.

**Rationale**: Enables templated K8s Job and CronJob creation from floe.yaml.

**Acceptance Criteria**:
- [ ] Chart: `charts/floe-jobs/`
- [ ] Job template: dbt run, dlt ingestion, quality checks
- [ ] CronJob template: scheduled pipeline execution
- [ ] Configurable: image, command, environment, resources
- [ ] Pod spec: security context, probes, volumes
- [ ] Values passed from floe compile output (CompiledArtifacts)
- [ ] Template validation: helm template succeeds

**Enforcement**:
- Chart template tests (renders without errors)
- Job creation tests (jobs deploy and execute)
- CronJob creation tests (schedules work)

**Constraints**:
- MUST use Helm templating for job generation
- MUST support dbt, dlt, and custom job types
- MUST NOT hardcode job specifications
- FORBIDDEN to use shell scripts to create manifests (use Helm)

**Test Coverage**: `tests/integration/test_helm_jobs_chart.py`

**Traceability**:
- REQ-602 (Job Execution Model)
- REQ-603 (CronJob Scheduling)

---

### REQ-628: Helm Release Versioning **[New]**

**Requirement**: System MUST manage Helm chart versions using semantic versioning aligned with floe releases.

**Rationale**: Enables reproducible deployments and version tracking.

**Acceptance Criteria**:
- [ ] Chart version: X.Y.Z (major.minor.patch)
- [ ] Chart appVersion: matches floe release version
- [ ] Version changes: MAJOR for breaking changes, MINOR for additions, PATCH for fixes
- [ ] Version validation: Helm rejects incompatible versions
- [ ] Release history: helm history shows previous chart releases
- [ ] Rollback: helm rollback reverts to previous chart version

**Enforcement**:
- Chart version validation tests
- appVersion consistency tests (matches software version)
- Rollback tests (previous release versions available)

**Constraints**:
- MUST use semantic versioning (X.Y.Z format)
- MUST increment version on any manifest change
- MUST maintain release history (Helm default)
- FORBIDDEN to use floating versions in production (e.g., v1.2.*)

**Test Coverage**: `tests/integration/test_helm_versioning.py`

**Traceability**:
- Semantic Versioning documentation
- Helm Release Management documentation

---

### REQ-629: Helm Hooks (Installation, Upgrade, Deletion) **[New]**

**Requirement**: System MAY define Helm hooks for pre/post deployment tasks (database migrations, backups).

**Rationale**: Enables automated lifecycle management without manual intervention.

**Acceptance Criteria**:
- [ ] pre-install hook: validate cluster prerequisites
- [ ] post-install hook: initialize database schema, create users
- [ ] pre-upgrade hook: backup database state
- [ ] post-upgrade hook: run migrations
- [ ] pre-delete hook: backup data before uninstall
- [ ] Hook resources cleaned up after execution (deletePolicy: before-hook-creation)

**Enforcement**:
- Hook execution tests (hooks run in correct order)
- Hook failure handling (clear error messages)
- Cleanup tests (hook resources removed after execution)

**Constraints**:
- MUST use Helm hooks (not manual scripts)
- MUST set appropriate deletePolicy (when to delete hook resources)
- MUST handle hook failures gracefully
- FORBIDDEN to rely on hooks for security-critical operations (use RBAC instead)

**Test Coverage**: `tests/integration/test_helm_hooks.py`

**Traceability**:
- Helm Hooks documentation
- Kubernetes Job hooks pattern

---

### REQ-630: Chart Repository and Distribution **[New]**

**Requirement**: System MUST publish Helm charts to OCI-based registry (GitHub Container Registry) for distribution.

**Rationale**: Enables easy installation and version management via standard Helm repository.

**Acceptance Criteria**:
- [ ] Charts published to GHCR: ghcr.io/anthropics/floe/charts
- [ ] Chart versions tagged: ghcr.io/anthropics/floe/charts/floe-platform:1.2.3
- [ ] Helm repo add: helm repo add floe oci://ghcr.io/anthropics/floe/charts
- [ ] Chart installation: helm install floe floe/floe-platform --version 1.2.3
- [ ] Release notes: document breaking changes per major version
- [ ] Chart signatures: signed charts (optional, security best practice)

**Enforcement**:
- Chart publication tests (charts successfully uploaded to registry)
- Chart discovery tests (helm repo list finds charts)
- Installation from repository tests

**Constraints**:
- MUST use OCI registry for chart distribution (not GitHub releases)
- MUST support semantic version constraints (helm install --version >=1.2,<2.0)
- MUST document chart breaking changes in release notes
- FORBIDDEN to force specific chart versions (allow flexibility)

**Test Coverage**: `tests/integration/test_helm_repository.py`

**Traceability**:
- Helm OCI Registry Support documentation
- GitHub Container Registry documentation

---

### REQ-631: Chart Linting and Validation **[New]**

**Requirement**: System MUST validate Helm charts with helm lint and custom validators.

**Rationale**: Catches chart errors before deployment.

**Acceptance Criteria**:
- [ ] helm lint: YAML syntax, schema validation, deprecated APIs
- [ ] helm template: renders templates without values errors
- [ ] Custom validators: required fields, resource limits validation
- [ ] Linting passes in CI: pre-commit hook or CI pipeline
- [ ] Linting fails deployment: invalid charts rejected

**Enforcement**:
- helm lint tests (no warnings or errors)
- helm template tests (renders successfully)
- Custom validator tests (catches common mistakes)
- CI integration tests (linting required before merge)

**Constraints**:
- MUST run helm lint in CI
- MUST resolve all helm lint errors (not ignore with --strict=false)
- MUST validate with custom validators (e.g., resource limits)
- FORBIDDEN to skip linting in production

**Test Coverage**: `tests/integration/test_helm_linting.py`

**Traceability**:
- Helm Linting documentation
- helm lint command documentation

---

### REQ-632: Helm Values Documentation **[New]**

**Requirement**: System MUST document all Helm values in chart README with descriptions, defaults, and validation rules.

**Rationale**: Enables users to understand and configure charts correctly.

**Acceptance Criteria**:
- [ ] values.yaml: documented comments for every configurable value
- [ ] README.md: table of values (name, description, default, range)
- [ ] Example: replicaCount, image.repository, resources.limits, etc.
- [ ] Breaking changes documented (major version changes)
- [ ] Configuration patterns documented (when to use which values)

**Enforcement**:
- Documentation completeness tests (all values documented)
- README generation from values.yaml (optional automation)
- Example deployment validation (README examples work)

**Constraints**:
- MUST document all configurable values
- MUST include validation ranges (e.g., replicaCount > 0)
- MUST provide example configurations
- FORBIDDEN to leave values undocumented

**Test Coverage**: `tests/integration/test_helm_documentation.py`

**Traceability**:
- Helm Best Practices
- README patterns for Helm charts

---

### REQ-633: Helm Conditional Features **[New]**

**Requirement**: System MUST support optional features via Helm conditions and enabled flags.

**Rationale**: Enables flexible deployments (optional: network policies, observability backends, ingress).

**Acceptance Criteria**:
- [ ] Conditions: networkPolicies.enabled, observability.enabled, ingress.enabled
- [ ] Conditional rendering: {{ if .Values.networkPolicies.enabled }}
- [ ] Default: sensible defaults (some features enabled, others optional)
- [ ] Example: deploy with/without ingress controller
- [ ] Chart.yaml: declares conditions explicitly

**Enforcement**:
- Conditional rendering tests (resources created when enabled)
- Conditional skip tests (resources not created when disabled)
- Default behavior tests (features enabled by default work)

**Constraints**:
- MUST use conditions for optional features (not required)
- MUST set sensible defaults (secure by default)
- MUST test all condition combinations
- FORBIDDEN to hide required features behind conditions

**Test Coverage**: `tests/integration/test_helm_conditions.py`

**Traceability**:
- Helm Conditions documentation
- Helm Templating best practices

---

### REQ-634: Service Mesh Integration (Optional) **[New]**

**Requirement**: System MAY support optional integration with Kubernetes service mesh (e.g., Istio, Linkerd) for advanced networking.

**Rationale**: Enables traffic management, circuit breaking, mTLS.

**Acceptance Criteria**:
- [ ] Mesh integration: optional via values.yaml (serviceMesh.enabled)
- [ ] Sidecar injection: automatically inject mesh sidecar (Istio: sidecar.istio.io/inject=true)
- [ ] VirtualService: define traffic routing (Istio)
- [ ] DestinationRule: define load balancing policies
- [ ] PeerAuthentication: mTLS configuration
- [ ] Mesh-agnostic design: works with or without mesh

**Enforcement**:
- Mesh integration tests (with mesh enabled)
- Mesh-optional tests (without mesh, works as before)
- Traffic routing tests (VirtualService applies)

**Constraints**:
- MUST make mesh optional (not required)
- MUST support both Istio and Linkerd (if implementing)
- MUST NOT break deployments without mesh
- FORBIDDEN to require mesh for basic functionality

**Test Coverage**: `tests/integration/test_helm_service_mesh.py`

**Traceability**:
- Istio Helm integration documentation
- Linkerd Helm integration documentation

---

### REQ-635: Helm Testing and Verification **[New]**

**Requirement**: System MUST provide helm test command with test pods to verify chart deployment.

**Rationale**: Enables post-deployment validation without external tools.

**Acceptance Criteria**:
- [ ] helm test: run validation tests after deployment
- [ ] Test pods: Helm test runner pods (e.g., curl, dbt validation)
- [ ] Tests verify: services are healthy, endpoints are reachable
- [ ] Test results: pass/fail reported, failed tests block deployment
- [ ] Example: test Dagster API, test Polaris catalog, test dbt connectivity

**Enforcement**:
- helm test execution tests (tests run and report results)
- Test failure detection (failed tests surface errors)
- Post-deployment validation

**Constraints**:
- MUST implement helm test (test resources in templates/tests/)
- MUST verify critical functionality (services, databases, connectivity)
- MUST fail deployment on test failure
- FORBIDDEN to make tests optional in production

**Test Coverage**: `tests/integration/test_helm_testing.py`

**Traceability**:
- Helm Test documentation
- Helm hooks testing pattern
