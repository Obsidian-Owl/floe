#!/usr/bin/env bash
#
# Validate Test Values Drift Detection
#
# This script verifies that values-test.yaml configurations are valid
# subsets of the main values.schema.json and don't introduce keys
# that don't exist in the schema.
#
# Requirements:
# - FR-095: Drift detection for test values
# - Python 3.8+
# - jsonschema, pyyaml packages
#
# Usage:
#   ./scripts/validate-test-values.sh [--strict]
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STRICT_MODE="${1:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Check prerequisites
check_prerequisites() {
    if ! command -v python3 &> /dev/null; then
        log_error "python3 is not installed"
        exit 1
    fi

    python3 -c "import jsonschema, yaml" 2>/dev/null || {
        log_error "Required Python packages missing. Install with: pip install jsonschema pyyaml"
        exit 1
    }
}

# Validate a single chart's test values
validate_chart() {
    local chart_name="$1"
    local chart_path="${PROJECT_ROOT}/charts/${chart_name}"
    local schema_file="${chart_path}/values.schema.json"
    local test_values="${chart_path}/values-test.yaml"

    if [[ ! -f "$schema_file" ]]; then
        log_warn "Schema file not found: $schema_file"
        return 0
    fi

    if [[ ! -f "$test_values" ]]; then
        log_warn "Test values file not found: $test_values"
        return 0
    fi

    log_info "Validating ${chart_name}/values-test.yaml..."

    python3 << PYTHON_SCRIPT
import json
import yaml
import jsonschema
import sys

def validate_values(schema_path, values_path, strict=False):
    """Validate values against schema with optional strict mode."""
    with open(schema_path) as f:
        schema = json.load(f)

    with open(values_path) as f:
        values = yaml.safe_load(f)

    if not values:
        print(f"  Empty values file: {values_path}")
        return True

    try:
        jsonschema.validate(values, schema)
        print(f"  ✓ Schema validation passed")
    except jsonschema.ValidationError as e:
        print(f"  ✗ Schema validation failed: {e.message}")
        return False

    if strict:
        # Check for keys not in schema (potential drift)
        def check_keys(obj, schema_props, path=""):
            warnings = []
            if isinstance(obj, dict) and isinstance(schema_props, dict):
                for key, value in obj.items():
                    key_path = f"{path}.{key}" if path else key
                    if key not in schema_props.get("properties", {}):
                        # Check additionalProperties
                        if not schema_props.get("additionalProperties", True):
                            warnings.append(f"Key '{key_path}' not in schema")
                    else:
                        nested_schema = schema_props["properties"][key]
                        warnings.extend(check_keys(value, nested_schema, key_path))
            return warnings

        warnings = check_keys(values, schema.get("properties", {}))
        if warnings:
            print("  Drift warnings (strict mode):")
            for w in warnings:
                print(f"    - {w}")

    return True

strict = "${STRICT_MODE}" == "--strict"
success = validate_values("${schema_file}", "${test_values}", strict)
sys.exit(0 if success else 1)
PYTHON_SCRIPT
}

main() {
    log_info "==========================================="
    log_info "Test Values Drift Detection"
    log_info "==========================================="

    check_prerequisites

    local failed=0

    # Validate floe-platform
    if ! validate_chart "floe-platform"; then
        failed=1
    fi

    # Validate floe-jobs
    if ! validate_chart "floe-jobs"; then
        failed=1
    fi

    echo ""
    if [[ "$failed" -eq 1 ]]; then
        log_error "==========================================="
        log_error "Drift detection: FAILED"
        log_error "==========================================="
        exit 1
    else
        log_info "==========================================="
        log_info "Drift detection: PASSED"
        log_info "==========================================="
    fi
}

main "$@"
