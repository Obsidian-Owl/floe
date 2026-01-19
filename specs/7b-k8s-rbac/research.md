# Research: K8s RBAC Plugin System

**Feature**: Epic 7B - K8s RBAC Plugin System
**Date**: 2026-01-19

## Prior Decisions (from Agent Memory)

From prior Epic 7A implementation:
- **Plugin ABC pattern**: All plugins extend `PluginMetadata` with abstract `name`, `version`, `floe_api_version` properties
- **Dataclass pattern**: Use `@dataclass` for simple result types (e.g., `TokenValidationResult`, `HealthStatus`)
- **Pydantic v2 pattern**: Use `BaseModel` with `ConfigDict(frozen=True, extra="forbid")` for configuration models
- **Base test class pattern**: `Base{Plugin}Tests` provides ABC compliance tests with `@pytest.mark.requirement()` markers

## Technology Choices

### Decision 1: RBACPlugin ABC Location

**Decision**: Place `RBACPlugin` ABC in `packages/floe-core/src/floe_core/plugins/rbac.py`

**Rationale**:
- Follows existing pattern (`identity.py`, `secrets.py` in same location)
- floe-core owns all plugin ABCs per constitution (Principle II)
- Entry point registration: `floe.rbac` group

**Alternatives Rejected**:
- Separate package (`floe-rbac-core`): Too much fragmentation for a core security feature
- Inside floe-cli: Would violate package boundaries

### Decision 2: Kubernetes Client Library

**Decision**: Use official `kubernetes` Python client library (v27+)

**Rationale**:
- Official Kubernetes client with full API coverage
- Supports in-cluster and kubeconfig authentication
- Matches K8s 1.28+ requirement from spec
- Already used in other K8s-native projects in ecosystem

**Alternatives Rejected**:
- `kr8s` (async): Would introduce async complexity not needed for RBAC generation
- `lightkube`: Less community support, smaller API coverage
- Pure YAML generation without client: Would lose validation capabilities

### Decision 3: YAML Generation Approach

**Decision**: Use Pydantic models serialized to YAML via `yaml.safe_dump(model.model_dump())`

**Rationale**:
- Pydantic provides validation before serialization
- Clean separation of data model from output format
- Follows constitution Principle IV (Contract-Driven Integration)
- Enables JSON Schema export for IDE autocomplete

**Alternatives Rejected**:
- Jinja2 templates: More error-prone, harder to test
- Direct dict manipulation: Loses type safety
- kubernetes client model serialization: Overly complex for static manifests

### Decision 4: Manifest Output Structure

**Decision**: Generate separate files per resource type in `target/rbac/` directory

**Rationale**:
- FR-053 requires: `serviceaccounts.yaml`, `roles.yaml`, `rolebindings.yaml`, `namespaces.yaml`
- Enables granular `kubectl apply` (e.g., apply only roles)
- Easier to audit and review
- Follows GitOps best practices for separation

**Alternatives Rejected**:
- Single combined manifest: Harder to audit, requires custom tooling to extract
- Kustomize overlays: Adds complexity not justified for this scope

### Decision 5: Test Base Class Structure

**Decision**: Create `BaseRBACPluginTests` in `testing/base_classes/base_rbac_plugin_tests.py`

**Rationale**:
- Follows established pattern from `BaseIdentityPluginTests`, `BaseSecretsPluginTests`
- Ensures all RBAC plugin implementations meet interface requirements
- Uses `@pytest.mark.requirement()` for traceability (FR-001 to FR-073)

**Alternatives Rejected**:
- Direct tests only: Would miss contract compliance checking
- pytest plugins: Overkill for this use case

## Integration Patterns

### Pattern 1: Compilation Pipeline Integration

The RBAC plugin integrates into the existing 6-stage compilation pipeline:

```
Stage 1: Load (manifest.yaml, floe.yaml)
Stage 2: Resolve (plugin configuration)
Stage 3: Validate (schema validation)
Stage 4: Transform (business logic)
Stage 5: Generate (dbt profiles, Dagster config)
Stage 6: OUTPUT → RBAC manifests (NEW)
```

**Integration point**: Add `RBACStage` after existing generation stages that:
1. Reads security configuration from manifest
2. Collects secret references from all data products
3. Generates RBAC manifests via `RBACManifestGenerator`
4. Writes to `target/rbac/` directory

### Pattern 2: CLI Command Integration

New subcommands under `floe rbac`:

```bash
floe rbac generate    # Generate RBAC manifests
floe rbac validate    # Validate against config
floe rbac audit       # Analyze cluster state
floe rbac diff        # Show drift
```

Implementation via argparse subparsers in existing CLI structure.

### Pattern 3: Secret Reference Resolution

RBAC generation depends on Epic 7A `SecretsPlugin`:

```python
# During compilation
for secret_ref in compiled_artifacts.secret_references:
    # Generate Role with get permission for this secret
    role_rules.append(RoleRule(
        apiGroups=[""],
        resources=["secrets"],
        verbs=["get"],
        resourceNames=[secret_ref.name]
    ))
```

## K8s API Compatibility

### Kubernetes 1.28+ Features Used

| Feature | K8s Version | Usage |
|---------|-------------|-------|
| Pod Security Admission | 1.25+ GA | Namespace labels for PSS enforcement |
| Bound Service Account Tokens | 1.22+ GA | Auto-rotated tokens, no secret creation |
| RBAC v1 | 1.8+ GA | Role, RoleBinding, ClusterRole resources |
| batch/v1 Job | 1.21+ GA | Job creation for data pipelines |

### API Groups and Resources

| Resource | API Group | Verbs Generated |
|----------|-----------|-----------------|
| ServiceAccount | v1 | create, get |
| Role | rbac.authorization.k8s.io/v1 | create, get |
| RoleBinding | rbac.authorization.k8s.io/v1 | create, get |
| Namespace | v1 | create, get |
| Secret | v1 | get (resourceNames constrained) |
| Job | batch/v1 | create, get, list, watch, delete |
| Pod | v1 | get, list, watch |
| Pod/log | v1 | get |
| ConfigMap | v1 | get (if referenced) |

## Security Considerations

### Least Privilege Implementation

Per FR-070 and FR-024, generated Roles follow these constraints:

1. **No wildcard permissions**: Never generate `*` for apiGroups, resources, or verbs
2. **resourceNames when possible**: Constrain to specific secret names
3. **Minimal verbs for secrets**: Only `get`, never `list`/`watch`/`create`/`update`/`delete`
4. **Namespace-scoped by default**: Prefer Role over ClusterRole

### Token Mounting Strategy (from Clarification)

Per FR-011 and FR-014:
- `automountServiceAccountToken: false` for pure compute jobs (dbt/dlt)
- `automountServiceAccountToken: true` only for jobs with `k8s_api_access: true`

### Pod Security Standards Alignment

Per ADR-0022 and FR-030 to FR-044:
- `floe-jobs`: `restricted` PSS by default
- `floe-platform`: `baseline` PSS for stateful services
- Domain namespaces: `restricted` by default

## Dependencies

### Package Dependencies

```toml
# In floe-core pyproject.toml
dependencies = [
    "kubernetes>=27.0.0,<29.0.0",  # K8s client for RBAC operations
    "pyyaml>=6.0",                  # YAML serialization (existing)
    "pydantic>=2.0.0,<3.0.0",       # Config models (existing)
]
```

### Epic Dependencies

| Dependency | Status | Impact |
|------------|--------|--------|
| Epic 7A (Identity & Secrets) | Complete | `SecretsPlugin` for secret reference resolution |
| Epic 2B (Compilation Pipeline) | Complete | Integration point for RBAC generation stage |
| Epic 7C (Network/Pod Security) | Future | Network policies (out of scope for 7B) |

## Open Questions (Resolved)

### Q1: Should token mounting be differentiated by pod type?
**Answer**: Yes (from /speckit.clarify). Pure compute jobs get `automountServiceAccountToken: false`.

### Q2: Where should the RBACPlugin ABC be located?
**Answer**: `packages/floe-core/src/floe_core/plugins/rbac.py` (follows existing pattern).

### Q3: How to handle existing RBAC resources in cluster?
**Answer**: Detect via labels (`app.kubernetes.io/managed-by: floe`), report conflicts, `--force` to overwrite.
