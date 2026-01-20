# Data Model: CLI Unification

**Epic**: 11 (CLI Unification)
**Date**: 2026-01-20

## CLI Command Hierarchy

```
floe                           # Root command group
├── --version                  # Show version
├── --help                     # Show help
│
├── platform/                  # Platform Team command group
│   ├── compile               # Build CompiledArtifacts
│   │   ├── --spec            # Path to floe.yaml
│   │   ├── --manifest        # Path to manifest.yaml
│   │   ├── --output          # Output path (default: target/compiled_artifacts.json)
│   │   ├── --enforcement-report  # Enforcement report output path
│   │   └── --enforcement-format  # Format: json|sarif|html
│   ├── test                  # Run policy tests (stub)
│   ├── publish               # Push to OCI registry (stub)
│   ├── deploy                # Deploy to K8s (stub)
│   └── status                # Check deployment status (stub)
│
├── rbac/                      # RBAC management group
│   ├── generate              # Generate RBAC manifests
│   │   ├── --config          # Path to manifest.yaml
│   │   ├── --output          # Output directory
│   │   └── --dry-run         # Preview without writing
│   ├── validate              # Validate RBAC configuration
│   │   ├── --config          # Path to manifest.yaml
│   │   ├── --manifest-dir    # Directory with RBAC manifests
│   │   └── --output          # Output format: text|json
│   ├── audit                 # Audit deployed RBAC
│   │   ├── --namespace       # K8s namespace
│   │   ├── --kubeconfig      # Kubeconfig path
│   │   └── --output          # Output format
│   └── diff                  # Compare expected vs deployed
│       ├── --manifest-dir    # Directory with RBAC manifests
│       ├── --namespace       # K8s namespace
│       ├── --kubeconfig      # Kubeconfig path
│       └── --output          # Output format
│
├── artifact/                  # Artifact management group
│   └── push                  # Push to OCI registry
│       ├── --artifact        # Path to compiled_artifacts.json
│       └── --registry        # OCI registry URL
│
├── compile                    # Data Team: validate spec (stub)
├── validate                   # Data Team: validate floe.yaml (stub)
├── run                        # Data Team: execute pipeline (stub)
└── test                       # Data Team: run dbt tests (stub)
```

## Entity Definitions

### Command

| Field | Type | Description |
|-------|------|-------------|
| name | str | Command name (e.g., "compile") |
| group | str | Parent group (e.g., "platform") |
| description | str | Short description for help text |
| options | list[Option] | Command options |
| callback | Callable | Function to execute |

### Option

| Field | Type | Description |
|-------|------|-------------|
| name | str | Option name (e.g., "--spec") |
| type | ClickType | Click type (Path, Choice, String, etc.) |
| required | bool | Whether option is required |
| default | Any | Default value if not provided |
| help | str | Help text for option |

### CommandResult

| Field | Type | Description |
|-------|------|-------------|
| exit_code | int | 0 for success, non-zero for failure |
| stdout | str | Standard output content |
| stderr | str | Error output content |

## State Transitions

### Compile Command Flow

```
[Start] → [Validate Inputs] → [Load Files] → [Compile] → [Export] → [Exit]
           ↓ (invalid)         ↓ (not found)   ↓ (error)   ↓ (error)
        [Error: stderr]     [Error: stderr]  [Error: stderr] [Error: stderr]
           ↓                    ↓               ↓             ↓
        [Exit 1]            [Exit 1]         [Exit 1]       [Exit 1]
```

### RBAC Generate Flow

```
[Start] → [Load Config] → [Generate Manifests] → [Write Files] → [Exit 0]
           ↓ (error)       ↓ (error)              ↓ (dry-run)
        [Error: stderr]  [Error: stderr]       [Preview Only]
           ↓                ↓                      ↓
        [Exit 1]         [Exit 1]              [Exit 0]
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (invalid input, file not found, etc.) |
| 2 | Command not found / usage error |

## Validation Rules

### Path Options
- Must be valid filesystem path
- Parent directory must exist for output paths (or will be created)
- Read paths must exist and be readable

### Choice Options
- `--enforcement-format`: Must be one of: json, sarif, html
- `--output` (rbac): Must be one of: text, json

### Required Options
- `floe platform compile --spec`: Required
- `floe platform compile --manifest`: Required
- `floe rbac generate --config`: Required
- `floe artifact push --artifact`: Required
- `floe artifact push --registry`: Required
