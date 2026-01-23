# Golden Test Fixtures

This directory contains golden test fixtures for behavior-preserving refactoring validation.

## Purpose

Golden tests capture the **exact output** of functions before refactoring, enabling verification that behavior is preserved after code changes.

## Structure

```
golden/
├── cli_rbac/              # Golden fixtures for CLI RBAC commands
│   └── diff_command/      # diff_command() function outputs
├── oci/                   # Golden fixtures for OCI client operations
│   └── pull/              # pull() method outputs
└── README.md              # This file
```

## Usage

### Creating Golden Fixtures

```python
from testing.base_classes.golden_test_utils import capture_golden_output

# Capture output before refactoring
capture_golden_output(
    func=diff_command,
    args={"old_spec": old_spec, "new_spec": new_spec},
    fixture_path="testing/fixtures/golden/cli_rbac/diff_command/basic_diff.json"
)
```

### Validating Against Golden Fixtures

```python
from testing.base_classes.golden_test_utils import assert_golden_match

# Verify output matches golden fixture after refactoring
result = diff_command(old_spec, new_spec)
assert_golden_match(result, "testing/fixtures/golden/cli_rbac/diff_command/basic_diff.json")
```

## Naming Convention

- `{module}/{function}/{scenario}.json` - JSON output
- `{module}/{function}/{scenario}.txt` - Text output
- `{module}/{function}/{scenario}_input.yaml` - Input fixtures

## Related Tasks

- T004: Create this directory structure
- T005: Create golden test runner utility
- T019: Create golden tests for diff_command()
- T020: Create golden tests for pull()
