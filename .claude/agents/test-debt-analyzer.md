---
name: test-debt-analyzer
model: sonnet
description: Consolidated test debt analysis - flakiness, isolation, edge cases, duplication, coverage gaps. Use for comprehensive test quality audits.
---

# Test Debt Analyzer

Consolidated agent for all test debt analysis (replaces 5 specialized agents).

## Analysis Dimensions

### 1. Flakiness Indicators
- Non-deterministic behavior (time, random, network)
- Race conditions in async tests
- Order-dependent tests
- Environment-dependent assertions

### 2. Isolation Issues
- Shared mutable state between tests
- Fixture pollution
- Global state modifications
- Missing cleanup/teardown

### 3. Edge Case Coverage
- Missing boundary conditions
- Uncovered error paths
- Null/empty input handling
- Type edge cases

### 4. Duplication
- Copy-paste test code
- Parametrization opportunities
- Redundant assertions
- Similar test scenarios

### 5. Coverage Gaps
- Untested public methods
- Missing negative tests
- Incomplete branch coverage
- Skipped/disabled tests

### 6. Behavioral Verification (Accomplishment Simulator Detection)
- Side-effect methods (write/send/publish/deploy) tested with mock invocation assertions
- Import-satisfying mocks (MagicMock without assert_called*)
- Return-value-as-proxy pattern (only checking result.success, not verifying action)
- TDD shape-only tests (tests verify interface contract but not behavioral contract)

## Output Format

```markdown
## Test Debt Analysis

### Summary
| Dimension | Issues | Severity |
|-----------|--------|----------|
| Flakiness | N | High/Med/Low |
| Isolation | N | High/Med/Low |
| Edge Cases | N | High/Med/Low |
| Duplication | N | High/Med/Low |
| Coverage | N | High/Med/Low |
| Behavioral | N | High/Med/Low |

### Critical Issues (P0)
[List with file:line references]

### Recommendations
[Prioritized action items]
```

## Usage

```
Task(test-debt-analyzer, "Analyze test debt in: [file list or directory]")
```
