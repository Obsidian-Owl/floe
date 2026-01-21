# CLI Commands Contract

**Epic**: 11 (CLI Unification)
**Date**: 2026-01-20
**Version**: 1.0.0

## Overview

This document defines the contract for CLI command interfaces. All commands MUST adhere to these specifications.

## General Contract

### Exit Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 0 | Success | Command completed successfully |
| 1 | General Error | Invalid input, file not found, operation failed |
| 2 | Usage Error | Invalid command syntax, unknown option |

### Output Streams

- **stdout**: Normal output (data, results, success messages)
- **stderr**: Error messages, warnings, diagnostic info

### Error Format

```
Error: <human readable message>
```

Errors MUST:
- Be plain text
- Start with "Error: "
- Be written to stderr
- Be one line (no multi-line errors)

## Command Contracts

### floe --version

**Input**: None
**Output**: Version string to stdout
**Format**: `floe-core <version>`
**Exit**: 0

### floe --help

**Input**: None
**Output**: Help text to stdout
**Exit**: 0

**Required Sections**:
- Usage line
- Description
- Commands list with descriptions
- Options list

### floe platform compile

**Required Options**:
- `--spec PATH`: Path to floe.yaml (required)
- `--manifest PATH`: Path to manifest.yaml (required)

**Optional Options**:
- `--output PATH`: Output path (default: target/compiled_artifacts.json)
- `--enforcement-report PATH`: Enforcement report output path
- `--enforcement-format CHOICE`: json|sarif|html (default: json)

**Success Output**:
- CompiledArtifacts written to output path
- If enforcement-report specified, report written to that path

**Exit Codes**:
- 0: Compilation successful
- 1: Compilation failed (validation error, file not found, etc.)

### floe rbac generate

**Required Options**:
- `--config PATH`: Path to manifest.yaml

**Optional Options**:
- `--output PATH`: Output directory (default: target/rbac/)
- `--dry-run`: Preview without writing files

**Success Output**:
- YAML files written to output directory
- Summary of generated resources to stdout

**Exit Codes**:
- 0: Generation successful
- 1: Generation failed

### floe rbac validate

**Required Options**:
- `--config PATH`: Path to manifest.yaml

**Optional Options**:
- `--manifest-dir PATH`: Directory with RBAC manifests
- `--output CHOICE`: text|json (default: text)

**Success Output**:
- Validation results to stdout
- Format depends on --output choice

**Exit Codes**:
- 0: Validation passed
- 1: Validation failed or error

### floe rbac audit

**Optional Options**:
- `--namespace TEXT`: K8s namespace to audit
- `--kubeconfig PATH`: Path to kubeconfig
- `--output CHOICE`: text|json (default: text)

**Success Output**:
- Audit report to stdout

**Exit Codes**:
- 0: Audit completed
- 1: Audit failed (K8s connection error, etc.)

### floe rbac diff

**Optional Options**:
- `--manifest-dir PATH`: Directory with expected manifests
- `--namespace TEXT`: K8s namespace
- `--kubeconfig PATH`: Path to kubeconfig
- `--output CHOICE`: text|json (default: text)

**Success Output**:
- Diff report showing added/removed/modified resources

**Exit Codes**:
- 0: Diff completed (no differences or differences found)
- 1: Diff failed (connection error, file not found)

### floe artifact push

**Required Options**:
- `--artifact PATH`: Path to compiled_artifacts.json
- `--registry URL`: OCI registry URL

**Authentication**:
Environment variables (in order of precedence):
1. `FLOE_REGISTRY_USERNAME` + `FLOE_REGISTRY_PASSWORD`: Explicit credentials
2. Docker credential helpers: `~/.docker/config.json` credHelpers
3. Anonymous: If no credentials configured (for public registries)

**Success Output**:
- Push confirmation with digest to stdout

**Exit Codes**:
- 0: Push successful
- 1: Push failed (auth error, network error, etc.)

### Stub Commands (Data Team)

The following commands are stubs pending full implementation:

| Command | Message | Exit Code |
|---------|---------|-----------|
| `floe compile` | "This command is not yet implemented. See floe platform compile for Platform Team usage." | 0 |
| `floe validate` | "This command is not yet implemented. See floe platform compile for Platform Team usage." | 0 |
| `floe run` | "This command is not yet implemented." | 0 |
| `floe test` | "This command is not yet implemented." | 0 |

**Stub Output Format**:
- Message written to stderr (informational, not error)
- Exit code 0 (command executed successfully, just has no implementation)
- No additional output

## Backward Compatibility

### RBAC Commands

The following outputs MUST be identical before and after migration:

1. `floe rbac generate --config <path> --output <dir>`
   - Same YAML files generated
   - Same file names
   - Same content (whitespace may differ)

2. `floe rbac validate --config <path>`
   - Same validation messages
   - Same exit codes for same inputs

3. `floe rbac audit --namespace <ns>`
   - Same audit report format
   - Same findings structure

4. `floe rbac diff --manifest-dir <dir> --namespace <ns>`
   - Same diff format
   - Same added/removed/modified reporting

## Golden File Locations

Baseline outputs are captured at:
```
tests/fixtures/cli/golden/
├── rbac_generate_output.txt
├── rbac_validate_output.txt
├── rbac_audit_output.txt
└── rbac_diff_output.txt
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-20 | Initial contract definition |
