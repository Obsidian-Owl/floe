# REQ-151 to REQ-152: Environment Context and Runtime Resolution

**Domain**: Configuration Management
**Priority**: CRITICAL
**Status**: New specification (Architectural Validation 2026-01-07)

## Overview

This group of requirements defines how environment context (dev/staging/prod) is handled in the two-tier configuration model. The key principle is **environment-agnostic compilation**: the same compiled artifact promotes across all environments, with environment-specific behavior determined at runtime via environment variables.

**Key Principle**: Compile once, deploy everywhere (12-Factor App)

## Requirements

### REQ-151: Environment Context Resolution **[New]**

**Requirement**: Compilation MUST be environment-agnostic. Environment context (dev/staging/prod) passed at runtime via `FLOE_ENV` environment variable. Same compiled artifact promotes across dev → staging → prod without recompilation.

**Rationale**: Environment-agnostic compilation enables immutable artifact promotion (ADR-0039), preventing environment-specific drift and reducing deployment complexity.

**Acceptance Criteria**:
- [ ] CompiledArtifacts schema does NOT contain `environment` field
- [ ] `floe run` reads `FLOE_ENV` environment variable (default: 'dev')
- [ ] Valid environments: `dev`, `staging`, `production`
- [ ] Environment context used ONLY for runtime credential resolution
- [ ] Compilation output identical regardless of target environment
- [ ] Environment validation at runtime (error if FLOE_ENV invalid)
- [ ] Compilation does NOT change based on environment

**Enforcement**:
- Compilation determinism tests (same input → same output across environments)
- CompiledArtifacts schema tests (no environment field)
- Runtime environment validation tests

**Constraints**:
- MUST NOT include environment field in CompiledArtifacts
- MUST NOT compile differently based on target environment
- FORBIDDEN to use `env_overrides` field (removed in unified manifest)

**Configuration Example**:
```yaml
# manifest.yaml (environment-agnostic)
plugins:
  compute:
    type: snowflake
    # NO environment-specific config here

  secrets:
    type: infisical
    # Environments defined in Infisical, not manifest
```

**Runtime Usage**:
```bash
# Development
export FLOE_ENV=dev
floe run customers

# Production (same compiled artifact)
export FLOE_ENV=production
floe run customers
```

**Test Coverage**:
- `tests/unit/test_compilation_determinism.py`
- `tests/contract/test_compiled_artifacts_schema.py::test_no_environment_field`

**Traceability**:
- ADR-0039 (Multi-Environment Promotion) - Immutable artifacts
- platform-enforcement.md lines 73-98 (Compilation workflow)
- Architectural validation finding: "env_overrides removed but replacement undefined"

---

### REQ-152: Environment-Specific Secret Resolution **[New]**

**Requirement**: SecretsPlugin MUST resolve credentials based on runtime `FLOE_ENV` value, not compile-time configuration. Same dbt profiles.yml and Dagster config work across all environments with just-in-time credential resolution.

**Rationale**: Runtime secret resolution enables single compiled artifact to work across dev/staging/prod without embedding environment-specific credentials.

**Acceptance Criteria**:
- [ ] SecretsPlugin.get_credential() receives `environment` parameter
- [ ] Environment parameter populated from `FLOE_ENV` at runtime
- [ ] Infisical environment mapping: `dev` → "dev", `staging` → "staging", `production` → "production"
- [ ] Vault path mapping: `dev` → "secret/data/dev/...", `production` → "secret/data/production/..."
- [ ] K8s Secrets namespace mapping: `dev` → secrets in dev namespace, `production` → prod namespace
- [ ] Same dbt profiles.yml template resolves different credentials per environment
- [ ] Error if credentials not found for target environment
- [ ] Credentials fetched just-in-time (not at compilation)

**Enforcement**:
- Secret resolution tests per environment
- dbt profiles credential resolution tests
- Multi-environment integration tests

**Constraints**:
- MUST fetch credentials at runtime, not compilation
- MUST validate environment before credential fetch
- FORBIDDEN to embed credentials in CompiledArtifacts

**Implementation Pattern**:
```python
# floe_core/compilation/profiles.py
def generate_dbt_profiles(compute_config: dict, secrets_plugin: SecretsPlugin) -> dict:
    """Generate dbt profiles with runtime credential resolution."""
    return {
        "floe": {
            "target": "{{ env_var('FLOE_ENV', 'dev') }}",  # Runtime environment
            "outputs": {
                "dev": {
                    "type": compute_config["type"],
                    "account": "{{ env_var('SNOWFLAKE_ACCOUNT') }}",  # Resolved at runtime
                    "user": "{{ env_var('SNOWFLAKE_USER') }}",
                    "password": "{{ env_var('SNOWFLAKE_PASSWORD') }}",  # From SecretsPlugin
                }
            }
        }
    }

# Runtime execution (floe-dagster)
def before_asset_execution(context):
    """Resolve credentials before dbt run."""
    environment = os.getenv("FLOE_ENV", "dev")

    # Fetch credentials from SecretsPlugin for this environment
    credentials = secrets_plugin.get_credential(
        name="snowflake-credentials",
        environment=environment  # Runtime resolution
    )

    # Set environment variables for dbt
    os.environ["SNOWFLAKE_ACCOUNT"] = credentials["account"]
    os.environ["SNOWFLAKE_USER"] = credentials["user"]
    os.environ["SNOWFLAKE_PASSWORD"] = credentials["password"]
```

**Infisical Configuration**:
```yaml
# Infisical project structure
# floe-platform (project)
#   ├── dev (environment)
#   │   ├── /compute/snowflake → SNOWFLAKE_PASSWORD=dev_password
#   │   └── /catalog/polaris → POLARIS_TOKEN=dev_token
#   ├── staging (environment)
#   │   ├── /compute/snowflake → SNOWFLAKE_PASSWORD=staging_password
#   │   └── /catalog/polaris → POLARIS_TOKEN=staging_token
#   └── production (environment)
#       ├── /compute/snowflake → SNOWFLAKE_PASSWORD=prod_password
#       └── /catalog/polaris → POLARIS_TOKEN=prod_token
```

**Test Coverage**:
- `tests/integration/test_secrets_environment_resolution.py`
- `tests/unit/test_dbt_profiles_generation.py::test_runtime_credential_resolution`

**Traceability**:
- ADR-0031 (Infisical Secrets Management) - Environment mapping
- ADR-0023 (Secrets Management) - SecretsPlugin interface
- REQ-131 to REQ-140 (Secrets Management requirements)
- Architectural validation finding: "Environment-specific configuration undefined"

---

## Migration from env_overrides

**Previous Pattern (Removed)**:
```yaml
# OLD: env_overrides field (DEPRECATED)
env_overrides:
  production:
    compute:
      warehouse: PROD_WAREHOUSE
```

**New Pattern (Runtime Resolution)**:
```yaml
# NEW: Environment-agnostic manifest
plugins:
  compute:
    type: snowflake
    warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE') }}"  # Runtime resolution

# Credentials resolved at runtime based on FLOE_ENV
```

**Runtime Environment Variables**:
```bash
# Development
export FLOE_ENV=dev
export SNOWFLAKE_WAREHOUSE=DEV_WAREHOUSE

# Production (same manifest, different runtime env)
export FLOE_ENV=production
export SNOWFLAKE_WAREHOUSE=PROD_WAREHOUSE
```

## Related Requirements

- **REQ-100 to REQ-115**: Unified Manifest Schema (no env_overrides)
- **REQ-131 to REQ-140**: Secrets Management (SecretsPlugin interface)
- **REQ-141 to REQ-150**: Compilation Workflow (environment-agnostic compilation)
- **REQ-326 to REQ-340**: Artifact Promotion (immutable artifacts across environments)

## References

- ADR-0039: Multi-Environment Promotion
- ADR-0031: Infisical Secrets Management
- 12-Factor App: III. Config (https://12factor.net/config)
- Architectural Validation Report (2026-01-07)
