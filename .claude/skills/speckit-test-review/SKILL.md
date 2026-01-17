---
name: speckit-test-review
description: Review test quality before PR - semantic analysis of test design, not just linting
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Usage Modes

| Mode | Command | Scope | When to Use |
|------|---------|-------|-------------|
| **Changed Files** | `/speckit.test-review` | Tests changed vs main | Before PR (default) |
| **Full Audit** | `/speckit.test-review --all` | ALL test files | Quality gate, periodic audit |
| **Specific Files** | `/speckit.test-review path/to/test.py` | Named files | Targeted review |

**Important**: Use `--all` to catch pre-existing issues, not just changes in current branch.

## Goal

Perform a comprehensive test quality review that answers: **Are these tests actually good tests?**

This is NOT linting. This is semantic analysis of test design:
- Do tests actually test what they claim?
- Could tests pass while the code is broken?
- Are tests at the right level?
- Are tests maintainable?

Plus floe-specific checks:
- Plugin testing completeness
- Contract stability
- Architecture compliance

## Operating Constraints

**STRICTLY READ-ONLY**: Do **not** modify any files. Output analysis and recommendations.

**SEMANTIC ANALYSIS**: Read and understand tests, don't just grep for patterns.

**TIERED OUTPUT**: Full analysis for problems, brief summary for clean tests.

## Memory Integration

### After Completion
Save quality findings:
```bash
./scripts/memory-save --decisions "Test review for {feature}: {key findings}" --issues "{LinearIDs}"
```

## Constitution Alignment

This skill validates test adherence to project principles:
- **TDD**: Tests should exist before implementation
- **Traceability**: Tests should have requirement markers
- **No Skip**: Tests should FAIL, not skip

## Execution Steps

### Phase 0: Identify Test Files

**You handle this phase directly.**

**Parse user input to determine mode:**

1. **If `--all` flag present**: Full codebase audit
   ```bash
   # Get ALL test files in the codebase
   find packages/*/tests plugins/*/tests tests/ testing/tests -name "test_*.py" -type f 2>/dev/null
   ```

2. **If specific file path provided**: Review that file
   ```bash
   # Verify file exists
   ls -la <provided-path>
   ```

3. **Default (no args)**: Changed files only
   ```bash
   # Get current branch
   git rev-parse --abbrev-ref HEAD

   # Get changed test files
   git diff --name-only main...HEAD | grep -E 'tests.*\.py$'
   ```

**Report mode to user:**
- `--all` mode: "Running FULL CODEBASE audit on N test files"
- Specific file: "Reviewing specified file: <path>"
- Default: "Reviewing N test files changed vs main"

If no test files to review in default mode, suggest using `--all` for full audit.

**Output**: List of test files to analyze, classified by type:
- Unit: `*/tests/unit/*.py` or no marker
- Integration: `*/tests/integration/*.py` or `@pytest.mark.integration`
- Contract: `*/tests/contract/*.py` or `@pytest.mark.contract`
- E2E: `*/tests/e2e/*.py` or `@pytest.mark.e2e`

### Phase 1: Semantic Test Analysis

**Invoke `test-reviewer` agent for each test file (or batch by type).**

```
Task(test-reviewer, "Review the following test file for quality, correctness, and maintainability.

File: [path]

Apply your full analysis framework:
1. For each test, evaluate Purpose, Correctness, Isolation, Maintainability, Type Appropriateness
2. Apply type-specific checks based on test classification
3. Full analysis for tests with issues, brief summary for clean tests

Return your structured analysis.")
```

**Wait for test-reviewer to return.**

### Phase 2: floe-Specific Analysis (Parallel)

**Invoke floe-specific agents IN PARALLEL (single message, multiple Task calls):**

```
Task(plugin-quality, "Analyze plugin testing completeness.
Changed files: [list]
Return your Plugin Quality Report.")

Task(contract-stability, "Analyze contract stability.
Changed files: [list]
Return your Contract Stability Report.")

Task(architecture-compliance, "Analyze architecture compliance in tests.
Changed files: [list]
Return your Architecture Compliance Report.")
```

**Wait for all agents to return.**

### Phase 3: Strategic Synthesis

**You handle this phase directly.**

Synthesize all reports into a unified strategic assessment.

## Output Format

```markdown
## Test Quality Review

**Branch**: [branch]
**Files Reviewed**: [N]
**Tests Analyzed**: [N]

---

### Executive Summary

| Aspect | Status | Key Finding |
|--------|--------|-------------|
| Test Design Quality | status | [summary from test-reviewer] |
| Plugin Coverage | status | [summary from plugin-quality] |
| Contract Stability | status | [summary from contract-stability] |
| Architecture Compliance | status | [summary from architecture-compliance] |

**Overall**: [One sentence assessment]

---

### Test Design Analysis

[Include test-reviewer findings]

#### Tests Needing Attention

[Full analysis for each problematic test]

#### Clean Tests

[Summary table of tests that passed review]

---

### floe-Specific Findings

#### Plugin Coverage
[Key findings from plugin-quality agent]

#### Contract Stability
[Key findings from contract-stability agent]

#### Architecture Compliance
[Key findings from architecture-compliance agent]

---

### Priority Actions

| Priority | Issue | Impact | Effort |
|----------|-------|--------|--------|
| P0 | [Must fix] | High | [estimate] |
| P1 | [Should fix] | Medium | [estimate] |
| P2 | [Consider] | Low | [estimate] |

---

### Recommendations

1. **Immediate** (this PR):
   - [Specific action with file:line]

2. **Follow-up** (next PR):
   - [Action item]

---

### Next Steps

- [ ] Address P0 issues
- [ ] Re-run `/speckit.test-review` to verify
- [ ] Proceed to PR when clean
```

## What This Review Checks

### From test-reviewer (Semantic Analysis)
- **Purpose**: Is it clear what's being tested?
- **Correctness**: Could test pass while code is broken?
- **Isolation**: Deterministic? Independent?
- **Maintainability**: Brittle to implementation changes?
- **Type Appropriateness**: Right level of test?

### From floe-specific agents
- **Plugin Quality**: All 11 types tested? Lifecycle coverage?
- **Contract Stability**: Schema stable? Backwards compatible?
- **Architecture**: K8s-native? Technology ownership respected?

## What This Review Does NOT Check

- **Linting/style**: ruff handles this
- **Type safety**: mypy handles this
- **Security**: Aikido/SonarQube handle this
- **Coverage %**: pytest-cov handles this

## When to Use

| Situation | Recommended Mode |
|-----------|------------------|
| Before creating a PR | `/speckit.test-review` (changed files) |
| After writing new tests | `/speckit.test-review` (changed files) |
| When investigating test failures | `/speckit.test-review path/to/test.py` |
| When asked "are my tests good?" | `/speckit.test-review --all` |
| **Quality gate / periodic audit** | `/speckit.test-review --all` |
| **Fixing pre-existing issues** | `/speckit.test-review --all` |

**Key Insight**: Default mode only reviews changed files. Use `--all` to catch issues that existed before your branch.

## Handoff

After completing this skill:
- **Fix issues**: Address P0/P1 issues identified
- **Check integration**: Run `/speckit.integration-check` before PR
- **Create PR**: Run `/speckit.pr` when tests pass

## References

- **`TESTING.md`** - Testing standards
- **`.claude/rules/testing-standards.md`** - Testing rules
- **`.claude/rules/test-organization.md`** - Test organization
