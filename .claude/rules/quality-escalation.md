# Quality Escalation Protocol (NON-NEGOTIABLE)

## Core Principle

**Claude is NOT empowered to make design decisions, architectural choices, or trade-offs autonomously.**

ALL assumptions about intent, approach, or trade-offs MUST be researched and presented to the user via `AskUserQuestion` with a proposed path forward. The ONLY autonomous actions permitted are mechanical tasks with objectively correct outcomes (formatting, type hints, clear bug fixes). Everything else — including design choices, technology decisions, workarounds, and quality trade-offs — requires explicit user approval.

Testing is the hard quality gate that validates these decisions. It must NEVER be weakened to accommodate a flawed assumption.

---

## HARD STOP Triggers

You MUST immediately stop and escalate via `AskUserQuestion` when ANY of these occur:

### 1. Design Decision or Trade-off

Any choice between two or more valid approaches, or any assumption about user intent.

**Indicators:**
- Choosing between technology approaches (e.g., monkey-patch vs K8s-native vs server config)
- Deciding how to structure code, APIs, or data models
- Making performance vs simplicity trade-offs
- Selecting error handling strategies
- Choosing configuration approaches
- Deciding scope (what to include/exclude)
- Assuming what the user "probably wants"

```
REQUIRED: Escalate to user
AskUserQuestion: "To resolve the S3 endpoint mismatch, there are three approaches:
  (A) Run tests inside K8s where hostnames resolve naturally — aligns with K8s-native principle
  (B) Monkey-patch the catalog at test time — quick but adds workaround code
  (C) Configure Polaris with split internal/external endpoints — clean but requires admin work
  Which approach should we take?"
```

### 2. Test Assertion Integrity Violation

A test fails and the impulse is to weaken the assertion rather than fix the code. Tests are the hard quality gate — they validate that design decisions were correct.

```python
# FORBIDDEN: Weakening a test to make it pass
# Before: assert table.scan().to_arrow().num_rows == 3
# After:  assert table is not None  # "simplified for reliability"

# REQUIRED: Escalate to user
AskUserQuestion: "Test `test_write_data` fails because table scan returns 0 rows.
  Root cause: PyIceberg REST catalog overrides client S3 endpoint with K8s-internal hostname.
  Options: (A) Fix S3 endpoint resolution, (B) Run tests inside K8s, (C) Monkey-patch catalog"
```

### 2. Workaround Introduction

Any code that works AROUND a problem rather than solving it.

**Indicators:**
- Monkey-patching private APIs (`obj._private_method = patched`)
- `except Exception: pass` to swallow errors
- Adding `pytest.skip()` because infrastructure is missing
- Replacing real service calls with mocks in integration tests
- Hardcoding values that should come from configuration

```
REQUIRED: Escalate to user
AskUserQuestion: "The Polaris REST catalog returns K8s-internal hostnames for S3.
  I could monkey-patch `catalog._load_file_io` to replace hostnames,
  but this is a workaround, not a solution. Should I:
  (A) Implement the monkey-patch with a TODO to fix properly
  (B) Run integration tests inside K8s where hostnames resolve
  (C) Configure Polaris with split internal/external endpoints"
```

### 3. Architectural Deviation

Any change that contradicts the constitution, component ownership rules, or established patterns.

**Indicators:**
- Importing from a package that violates ownership boundaries
- Creating ad-hoc integration formats instead of using contracts
- Putting tests in wrong tier/location
- Skipping quality gates to "get things working"

### 4. Spec/Plan Deviation

Implementation diverges from the approved spec or plan.

**Indicators:**
- Implementing fewer tests than planned
- Changing test strategy from real services to mocks
- Dropping requirements coverage
- Simplifying functionality beyond what was specified

### 5. Infrastructure Assumption

Making assumptions about infrastructure availability, configuration, or behavior.

**Indicators:**
- Assuming a service is reachable at a hardcoded address
- Assuming credentials match a specific environment
- Assuming bucket/namespace/catalog exists
- Assuming K8s DNS resolution works from host

---

## Decision Authority Matrix

### Autonomous (no escalation needed)
These have objectively correct outcomes — no judgment calls:

| Decision Type | Required Action |
|---------------|-----------------|
| Code formatting, style | Follow ruff/black |
| Import ordering | Follow ruff isort |
| Type hint additions | Follow mypy --strict |
| Bug fix with clear, single root cause | Fix and verify |
| Docstring additions | Follow Google style |

### MUST Escalate (user approval required)
These involve judgment, trade-offs, or assumptions:

| Decision Type | Required Action |
|---------------|-----------------|
| **Design choice** (>1 valid approach) | Present options with trade-offs |
| **Technology/library selection** | Research and present options |
| **API or data model design** | Present proposal for approval |
| **Error handling strategy** | Present approach for approval |
| **Scope decisions** (include/exclude) | Confirm with user |
| **Configuration approach** | Present options |
| **Dependency addition** | Present options with trade-offs |
| **New file creation** (unplanned) | Explain why needed |
| **Infrastructure assumptions** | Present evidence, ask for confirmation |

### NEVER Autonomous (hard prohibition)
These degrade quality or hide problems:

| Decision Type | Required Action |
|---------------|-----------------|
| **Weaken test assertions** | Escalate — the code is wrong, not the test |
| **Introduce workarounds** | Escalate with root cause + options |
| **Deviate from spec/plan** | Escalate with analysis of why |
| **Replace real services with mocks** | Escalate with rationale |
| **Skip quality gates** | Escalate — explain what's blocking |
| **Architectural deviation** | Escalate with constitution reference |

---

## Escalation Format

When escalating, use `AskUserQuestion` with this structure:

1. **What happened**: Factual description of the problem
2. **Root cause**: Technical analysis of why
3. **Options**: 2-4 concrete paths forward with trade-offs
4. **Recommendation**: Which option you'd suggest and why

```
AskUserQuestion:
  question: "Integration test fails because PyIceberg REST catalog
    overrides client S3 endpoint with K8s-internal hostname.
    Which approach should we take?"
  options:
    - label: "Run tests inside K8s (Recommended)"
      description: "Tests run where hostnames resolve naturally. Aligns with K8s-native principle."
    - label: "Monkey-patch catalog endpoint"
      description: "Quick fix, but introduces test-only workaround code."
    - label: "Configure Polaris split endpoints"
      description: "Server-side fix, requires Polaris admin changes."
```

---

## Anti-Patterns (FORBIDDEN)

### The Silent Architect

Making design decisions without asking. This is the **most common and most damaging** anti-pattern:
```
# User asked: "Fix the S3 endpoint issue"
# Claude silently chose: monkey-patch approach
# Should have asked: "There are 3 approaches — which do you prefer?"
```

### The Unopposed Assumption

Embedding assumptions about intent, scope, or approach without confirming:
```python
# Instead of asking: "Which bucket should integration tests use?"
bucket = "floe-warehouse"  # "assumed from convention"

# Instead of asking: "Should we use REST or gRPC for this service?"
# Silently implements REST because "it's simpler"
```

### The Silent Softener

Weakening test assertions without telling the user:
```python
# Started as:
assert scanned.num_rows == 3
assert set(scanned["name"].to_pylist()) == {"Alice", "Bob", "Charlie"}

# Silently became:
assert scanned is not None  # "table exists"
```

### The Exception Swallower

Hiding errors to make code work:
```python
try:
    result = real_service_call()
except Exception:
    pass  # "service sometimes unavailable"
```

### The Mock Smuggler

Replacing real services with mocks in integration tests:
```python
# Plan said: "real Polaris + real MinIO"
# Implementation uses: MagicMock for table_manager
```

### The Scope Reducer

Implementing less than planned without escalating:
```
# Plan: 6 real integration tests
# Delivered: 3 tests + "remaining tests can be added later"
```

### The Complexity Absorber

Solving a hard problem with complex code instead of escalating the underlying design question:
```python
# Instead of asking: "The server overrides client S3 config — is this the right architecture?"
# Writes 30 lines of monkey-patching to work around it
```

---

## Tracking Unresolved Issues

When escalation identifies a problem that won't be fixed immediately:

1. **Create a GitHub Issue** in the repo with label `tech-debt` or `architecture`
2. **Add a code comment** with the issue reference: `# TODO(FLO-XXX): description`
3. **Record in session notes** via `bd update` or notepad

NEVER leave a workaround without a tracking issue.

---

## Enforcement

This rule is enforced by:
- **Pre-PR review** (`/speckit.test-review`): Checks for assertion weakening
- **Architect verification**: Final gate before completion claims
- **Critic agent**: Reviews for workaround anti-patterns
- **Constitution compliance**: PR review checks for principle violations

**When in doubt, escalate. The cost of a 30-second question is far lower than the cost of a hidden bug.**
