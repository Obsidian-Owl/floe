# SonarQube Code Quality Standards

## Overview

This project uses SonarQube Cloud for code quality and security analysis. All code MUST pass
the Quality Gate before merging. AI-generated code is held to the same standards as
human-written code.

**Quality Gate Requirements:**
- Security Rating: A (no new vulnerabilities)
- Reliability Rating: A (no new bugs)
- Maintainability Rating: A (no new code smells exceeding threshold)
- Security Hotspots Reviewed: 100%
- Duplicated Lines: < 3%

---

## Common SonarQube Issues (PREVENT THESE)

The following rules are frequently triggered. ALWAYS follow these patterns to avoid issues.

### S6437: Credentials in Code (BLOCKER)

**Problem**: Hardcoded passwords, API keys, or secrets in source code.

```python
# ❌ FORBIDDEN - Triggers S6437
# password = "<hardcoded-value>"  # NEVER DO THIS
# wrong_password = "<test-credential>"  # ALSO FORBIDDEN

# ✅ CORRECT - Use environment variables
password = os.environ.get("DB_PASSWORD", "")
test_password = os.environ.get("TEST_INVALID_PASSWORD", "placeholder")
```

**Rule**: NEVER hardcode secrets, even in tests. Use environment variables with fallbacks.

---

### S1192: Duplicate String Literals (CRITICAL)

**Problem**: Same string literal appears 3+ times in a file.

```python
# ❌ FORBIDDEN - Triggers S1192
class Model1(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")  # Duplicate 1

class Model2(BaseModel):
    identifier: str = Field(..., pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")  # Duplicate 2

class Model3(BaseModel):
    code: str = Field(..., pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")  # Duplicate 3

# ✅ CORRECT - Define constant at module level
IDENTIFIER_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_]*$"
"""Regex pattern for valid identifiers."""

class Model1(BaseModel):
    name: str = Field(..., pattern=IDENTIFIER_PATTERN)

class Model2(BaseModel):
    identifier: str = Field(..., pattern=IDENTIFIER_PATTERN)

class Model3(BaseModel):
    code: str = Field(..., pattern=IDENTIFIER_PATTERN)
```

**Rule**: Extract repeated string literals (3+ occurrences) into module-level constants with docstrings.

---

### S1244: Float Equality Comparison (MAJOR)

**Problem**: Using `==` to compare floating-point numbers.

```python
# ❌ FORBIDDEN - Triggers S1244
assert timeout == 1.0
assert ratio == 0.5

# ✅ CORRECT - Use pytest.approx or math.isclose
import pytest
import math

assert timeout == pytest.approx(1.0)
assert math.isclose(ratio, 0.5, rel_tol=1e-9)
```

**Rule**: NEVER use `==` for float comparison. Use `pytest.approx()` in tests or `math.isclose()` in production.

---

### S108: Empty Code Blocks (MAJOR)

**Problem**: Empty blocks that serve no purpose.

```python
# ❌ FORBIDDEN - Triggers S108
if TYPE_CHECKING:
    pass  # Empty block

try:
    something()
except Exception:
    pass  # Swallowing exception

# ✅ CORRECT - Remove empty blocks or add content
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator  # Has actual import

# Or remove entirely if not needed
# (no if TYPE_CHECKING block at all)

try:
    something()
except SpecificException as e:
    logger.warning("Operation failed", error=str(e))
```

**Rule**: Never leave empty code blocks. Either add meaningful content or remove the block entirely.

---

### S5727: Identity Check Always True/False (CRITICAL)

**Problem**: Using `is not None` on a value just created that can never be None.

```python
# ❌ FORBIDDEN - Triggers S5727
span = create_span(name="test")  # Always returns a Span
assert span is not None  # Trivially true, SonarQube flags it

# ✅ CORRECT - Assert meaningful properties
span = create_span(name="test")
assert span.name == "test"  # Tests actual behavior
assert span.trace_id is not None  # This IS meaningful if trace_id can be None
```

**Rule**: Don't assert `is not None` on values that can never be None. Assert meaningful properties instead.

---

### S5655: Type Mismatch (CRITICAL)

**Problem**: Passing wrong types to functions (e.g., None when type hint doesn't allow it).

```python
# ❌ FORBIDDEN - Triggers S5655
def create_child_span(parent: Span, name: str) -> Span:
    ...

# This passes None but type hint requires Span
child = create_child_span(None, "test")  # type: ignore[arg-type]

# ✅ CORRECT - Update function signature to accept None
def create_child_span(parent: Span | None, name: str) -> Span | None:
    """Create child span, or None if parent is None."""
    if parent is None:
        return None
    ...

child = create_child_span(None, "test")  # Now type-safe
```

**Rule**: Don't use `# type: ignore` to bypass type checks. Update function signatures to be accurate.

---

### S1481: Unused Local Variables (MINOR)

**Problem**: Variables assigned but never used.

```python
# ❌ FORBIDDEN - Triggers S1481
total = 0
for item in items:
    process(item)
# total is never used

# ✅ CORRECT - Remove or use the variable
for item in items:
    process(item)

# Or if variable is intentionally unused (e.g., tuple unpacking):
_, second, _ = get_triple()  # Use underscore prefix
```

**Rule**: Remove unused variables. Use `_` prefix for intentionally ignored values.

---

### S7688/S7677: Shell Script Issues (MAJOR)

**Problem**: Using `[` instead of `[[` and not redirecting errors to stderr.

```bash
# ❌ FORBIDDEN - Triggers S7688
if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "ERROR: Something failed"  # S7677: Errors should go to stderr
fi

# ✅ CORRECT - Use [[ and redirect errors to stderr
if [[ $ATTEMPT -eq $MAX_ATTEMPTS ]]; then
    echo "ERROR: Something failed" >&2
fi
```

**Rule**: In bash scripts, use `[[` for conditionals and redirect errors to stderr with `>&2`.

---

## Security Hotspots

Security hotspots require manual review. Address these proactively:

### Hard-coded Credentials (S6418)

```python
# ❌ Security hotspot
# api_key = "<hardcoded-key>"  # NEVER DO THIS

# ✅ Use SecretStr and environment
from pydantic import SecretStr
api_key: SecretStr = SecretStr(os.environ["API_KEY"])
```

### Command Injection (S6350, S4721)

```python
# ❌ Security hotspot
subprocess.run(f"ls {user_input}", shell=True)

# ✅ Use list form, no shell
subprocess.run(["ls", user_input], shell=False, check=True)
```

### Weak Cryptography (S4790)

```python
# ❌ Security hotspot
hashlib.md5(data)  # Weak hash
hashlib.sha1(data)  # Weak hash

# ✅ Use strong algorithms
hashlib.sha256(data)
hashlib.sha3_256(data)
```

---

## Pre-Commit Quality Checklist

Before committing, mentally verify:

1. **No hardcoded secrets** - All credentials from environment variables
2. **No duplicate literals** - Repeated strings (3+) extracted to constants
3. **No float equality** - Using `pytest.approx()` or `math.isclose()`
4. **No empty blocks** - All blocks have meaningful content
5. **No trivial assertions** - Testing actual behavior, not existence
6. **Type hints accurate** - Function signatures match actual usage
7. **No unused variables** - All variables used or prefixed with `_`
8. **Bash uses [[** - Double brackets for conditionals
9. **Errors to stderr** - Error messages redirect with `>&2`

---

## Running SonarQube Locally

```bash
# Use the SonarQube MCP server for real-time feedback
# The MCP server is already configured in this project

# Check issues for a project
mcp__sonarqube__search_sonar_issues_in_projects

# Check quality gate status for PR
mcp__sonarqube__get_project_quality_gate_status --projectKey Obsidian-Owl_floe-runtime --pullRequest <PR_NUMBER>
```

---

## AI Code Quality Profile

Per SonarQube recommendations for AI-generated code:

1. **Use "Sonar way" profile** - Contains optimal rules for AI code
2. **Review all issues** - AI code is not exempt from quality standards
3. **Check security hotspots** - 100% must be reviewed
4. **Verify no false positives** - Don't blindly suppress warnings

**Remember**: AI-generated code often exhibits:
- Overly verbose comments (remove unnecessary ones)
- Uniform coding styles (good, but watch for repetition)
- Complex solutions to simple problems (simplify)
- Repetitive structures (extract to functions/constants)

---

## References

- [SonarQube Python Rules](https://rules.sonarsource.com/python/)
- [SonarQube AI Code Assurance](https://www.sonarsource.com/solutions/ai/ai-code-assurance/)
- [SonarQube Quality Profiles for AI Code](https://docs.sonarsource.com/sonarqube-server/2025.5/quality-standards-administration/ai-code-assurance/quality-profiles-for-ai-code)
