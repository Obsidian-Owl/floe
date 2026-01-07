---
description: Second-level architectural review validating alignment to target architecture (docs/)
---

## User Input

```text
$ARGUMENTS
```

You MUST consider the user input before proceeding (if not empty).

## Architectural Review Command

You are conducting a **second-level architectural review** to validate that feature branch changes align with floe-runtime's **target architecture** (documented in `docs/`) and prevent known anti-patterns.

**Your Role**: Act as a guard rail against tech debt from pragmatic AI solutions while enabling refactoring toward target state.

## Step 1: Read Target Architecture Documentation

Read and internalize the authoritative architectural documentation:

**Core Architecture** (Target State):
- `docs/four-layer-overview.md` - Four-layer architecture (Layer 1-4 boundaries, configuration flow)
- `docs/platform-enforcement.md` - Platform governance model, compile-time validation
- `docs/plugin-architecture.md` - Plugin system design, entry points, ABCs
- `docs/opinionation-boundaries.md` - ENFORCED vs PLUGGABLE decisions
- `docs/data-contracts.md` - Data contract architecture, ODCS standard

**Development Standards**:
- `CLAUDE.md` - Technology ownership table, CompiledArtifacts contract, standalone-first
- `.claude/rules/component-ownership.md` - Detailed ownership boundaries
- `.claude/rules/pydantic-contracts.md` - Contract patterns, Pydantic v2 syntax
- `.claude/rules/security.md` - Security standards, secret management
- `.claude/rules/testing-standards.md` - Testing requirements, no skipped tests
- `.claude/rules/standalone-first.md` - Standalone-first philosophy

Extract key architectural principles, invariants, and documented anti-patterns.

## Step 2: Analyze Git Changes

Parse user input for base and target branches (default: current branch vs `main`).

Run git commands to get changed files:
```bash
# Get base branch (default: main)
BASE=${BASE_BRANCH:-main}

# Get list of changed files
git diff --name-status $BASE...HEAD

# Get actual changes
git diff $BASE...HEAD
```

Categorize changes by:
- **Package**: floe-core, floe-dagster, floe-dbt, floe-iceberg, floe-polaris, floe-cube, floe-cli
- **Layer**: Layer 1 (foundation), Layer 2 (configuration), Layer 3 (services), Layer 4 (data)
- **File type**: Python (.py), SQL (.sql), YAML (.yaml/.yml), Markdown (.md), Config (.toml)

## Step 3: Research & Validate (Adaptive Analysis)

**IMPORTANT**: You have flexibility to research beyond just checking against docs. Use all available tools to provide comprehensive architectural review.

### 3a. Research Code Patterns

Use Explore, Grep, and Read tools to understand existing patterns:
- How is this pattern currently implemented elsewhere in the codebase?
- Are there existing examples of the correct approach?
- What similar changes have been made previously?
- Are there inconsistencies? (e.g., "this file does X, but 5 other files do Y")

### 3b. Validate Against Documentation

Compare changes against architectural principles extracted from docs. **These are examples - read the docs for the complete list**:

**Four-Layer Architecture** (`docs/four-layer-overview.md`):
- ❌ Does Layer 4 (data) modify Layer 2 (configuration)? → CRITICAL (breaks immutability)
- ❌ Do packages have upward imports (Layer 1 importing Layer 2)? → CRITICAL (circular dependency)
- ❌ Does configuration flow upward instead of downward? → CRITICAL (violates core invariant)
- ❌ Are dbt runs deployed as Deployments instead of Jobs? → HIGH (wrong lifecycle)

**Technology Ownership** (`CLAUDE.md`):
- ❌ Is SQL parsed in Python (outside floe-dbt)? → CRITICAL ("dbt owns SQL" principle)
- ❌ Are hardcoded S3 paths in dbt models? → HIGH (platform resolves storage)
- ❌ Is SQL executed in Dagster assets? → CRITICAL (use dbt instead)
- ❌ Does Polaris code write to storage directly? → HIGH (catalog manages storage)

**Contract Compliance** (`.claude/rules/pydantic-contracts.md`):
- ❌ Is FloeSpec passed between packages (instead of CompiledArtifacts)? → CRITICAL (violates contract)
- ❌ Are packages importing from each other (except CompiledArtifacts)? → HIGH (breaks isolation)
- ❌ Do models use Pydantic v1 syntax (@validator vs @field_validator)? → MEDIUM (use v2)

**Security** (`.claude/rules/security.md`):
- ❌ Are secrets hardcoded (passwords, API keys, tokens)? → CRITICAL (security breach)
- ❌ Is eval(), exec(), or pickle.loads() used on untrusted data? → CRITICAL (injection risk)
- ❌ Is subprocess.run(..., shell=True) used? → HIGH (command injection)
- ❌ Are credentials in CompiledArtifacts (should be SecretReference)? → CRITICAL (compile-time secrets)

**Testing Standards** (`.claude/rules/testing-standards.md`):
- ❌ Are tests skipped (pytest.skip, @pytest.mark.skip)? → HIGH (hidden failures)
- ❌ Is time.sleep() used in tests? → MEDIUM (use wait_for_condition)
- ❌ Are tests missing requirement markers (@pytest.mark.requirement)? → MEDIUM (no traceability)
- ❌ Are float comparisons using == instead of pytest.approx()? → MEDIUM (flaky tests)

**Standalone-First** (`.claude/rules/standalone-first.md`):
- ❌ Do features require SaaS Control Plane without graceful degradation? → MEDIUM (breaks standalone)
- ❌ Are proprietary formats used instead of standards (Iceberg, OpenLineage, OTel)? → HIGH (vendor lock-in)

### 3c. Validate Against Industry Best Practices (WebSearch)

**CRITICAL**: Use WebSearch to validate that documented patterns are still current best practices.

For significant architectural patterns, search for:
- "data platform architecture best practices 2026"
- "[technology] best practices 2026" (e.g., "dbt best practices 2026", "Dagster best practices 2026")
- "[pattern] anti-patterns" (e.g., "layer architecture anti-patterns", "plugin architecture anti-patterns")

**If documentation contradicts current best practices**, report as a finding:
```
MEDIUM: Documentation May Be Outdated

Source: docs/xyz.md recommends [pattern]
Research: WebSearch results (2026) show current best practice is [different pattern]
Details: [Summary of web search findings with links]

Recommendation: Review and consider updating documentation to align with current industry standards.

References:
- [Link 1 from web search]
- [Link 2 from web search]
```

### 3d. Think Critically

**Don't just validate "does code match docs"**. Also consider:

1. **Is our documented pattern still optimal?** Technology and practices evolve. If you find evidence that our architecture is outdated, report it.

2. **Does the change improve architecture even if it deviates from docs?** Sometimes innovation is valuable. If a deviation is actually an improvement, note it as a positive finding.

3. **Are there patterns in the change that we should document?** New best practices to capture for future development.

**Output findings for all three scenarios**:
- **Code violates documented architecture** → CRITICAL/HIGH (fix code)
- **Documented architecture contradicts best practices** → MEDIUM (update docs)
- **Change introduces new valuable pattern** → LOW (consider documenting)

### 3e. Check for Escape Hatches

Respect `# arch-review: ignore CODE - reason` comments in code.

If a violation has an escape hatch comment, note it in the report but lower severity:
```python
# arch-review: ignore TECH-001 - SQL parsing required for legacy migration compatibility
import sqlparse  # Valid exception with justification
```

Report as: `INFO: Violation suppressed with justification - verify reason is still valid`

## Step 4: Assess Persona Impact

For each finding, analyze impact on the four key personas:

**Data Engineers** (Primary Persona):
- **Cognitive Load**: Does this change reduce or increase cognitive load for data engineers?
- **DX**: Does it follow clear principles like "dbt owns SQL"?
- **Clarity**: Are error messages clear and actionable?
- **Workflow**: Does it simplify the data engineering workflow?

**Platform Engineers**:
- **Consistency**: Does this maintain platform-level consistency across environments?
- **Governance**: Are governance policies enforceable at compile-time?
- **Immutability**: Is configuration immutable and versioned (Layer 2)?
- **Multi-env**: Does it support dev/staging/prod deployment?

**DevOps Engineers / SREs**:
- **K8s-native**: Is the change Kubernetes-native and cloud-agnostic?
- **Observability**: Does it support observability (OpenTelemetry, OpenLineage)?
- **Declarative**: Are deployments declarative and reproducible?
- **Reliability**: Are health checks, readiness probes present? Stateless where required?

**Security Engineers**:
- **Credentials**: Are credentials managed securely (SecretReference, runtime resolution)?
- **Secrets**: No hardcoded secrets or PII in code?
- **Injection**: Are dangerous constructs avoided (eval, shell=True, pickle)?
- **Validation**: Is input validation comprehensive (Pydantic)?

Score each persona impact:
- ✅ **Positive** - Improves experience/capabilities
- ⚠️ **Neutral** - No significant impact
- ❌ **Negative** - Introduces problems/complexity

## Step 5: Generate Reports

### Terminal Summary (Concise, Colored)

Output a concise terminal summary using this format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ARCHITECTURAL REVIEW REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Branch:      [target] → [base]
Files:       [N] changed (+XXX, -YYY lines)
Timestamp:   YYYY-MM-DD HH:MM:SS UTC

SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CRITICAL: [N]   HIGH: [N]   MEDIUM: [N]   LOW: [N]   INFO: [N]

CRITICAL ISSUES ([N])
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [List each CRITICAL finding with file:line, brief description]

HIGH SEVERITY ([N])
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [List each HIGH finding with file:line, brief description]

MEDIUM SEVERITY ([N])
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [First 3 MEDIUM findings - see report for full list]

PERSONA IMPACT ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Data Engineers:      ✅ [N]  ⚠️ [N]  ❌ [N]  (Net: [Positive/Neutral/Negative])
  Platform Engineers:  ✅ [N]  ⚠️ [N]  ❌ [N]  (Net: [Positive/Neutral/Negative])
  DevOps/SREs:        ✅ [N]  ⚠️ [N]  ❌ [N]  (Net: [Positive/Neutral/Negative])
  Security:           ✅ [N]  ⚠️ [N]  ❌ [N]  (Net: [Positive/Neutral/Negative])

TOP RECOMMENDATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. [Most important action with doc reference]
  2. [Second most important action with doc reference]
  3. [Third most important action with doc reference]

Full report: .claude/reviews/arch-review-YYYYMMDD-HHMMSS.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STATUS: ADVISORY (non-blocking) - Review findings before PR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Markdown Report (Detailed)

Save a detailed markdown report to `.claude/reviews/arch-review-YYYYMMDD-HHMMSS.md`:

```markdown
# Architectural Review Report

**Branch**: [target] → [base]
**Timestamp**: YYYY-MM-DD HH:MM:SS UTC
**Reviewer**: Claude Code (Architectural Review Command)
**Status**: ADVISORY (non-blocking)

## Executive Summary

[2-3 paragraph summary of overall architectural alignment, major themes in findings, and net persona impacts]

### Architectural Alignment Score

| Dimension | Score | Assessment |
|-----------|-------|------------|
| Layer Boundaries | [XX]% | [Brief assessment] |
| Technology Ownership | [XX]% | [Brief assessment] |
| Contract Compliance | [XX]% | [Brief assessment] |
| Security Posture | [XX]% | [Brief assessment] |
| Testing Standards | [XX]% | [Brief assessment] |
| Standalone-First | [XX]% | [Brief assessment] |

**Overall Alignment**: [XX]% (Excellent/Strong/Moderate/Poor)

---

## Findings by Severity

### CRITICAL ([N])

#### [CRIT-001] [Finding Title]

**Location**: `path/to/file.py:45`
**Category**: [Layer Boundaries / Technology Ownership / Security / etc.]
**Source**: [docs/xyz.md or CLAUDE.md or .claude/rules/xyz.md]

**Issue**:
[Detailed description of the violation]

**Code Snippet**:
```python
[Relevant code showing the violation]
```

**Why This Matters**:
[Explanation of why this is CRITICAL - what breaks, what risk it introduces]

**Recommendation**:
[Specific, actionable fix with code example if applicable]

**Persona Impact**:
- Data Engineers: [Impact description]
- Platform Engineers: [Impact description]
- DevOps/SREs: [Impact description]
- Security: [Impact description]

---

### HIGH ([N])

[Same structure as CRITICAL]

---

### MEDIUM ([N])

[Same structure, can be more concise]

---

### LOW ([N])

[Same structure, brief]

---

### INFO ([N])

[Suppressed violations, positive findings, suggestions for documentation]

---

## Persona Impact Analysis

### Data Engineers (Primary Persona)

**Summary**: [Net impact assessment - Positive/Neutral/Negative]

**Positive Impacts** (✅ [N]):
- [FIND-XXX]: [Brief description of positive impact]
- [FIND-YYY]: [Brief description]

**Neutral** (⚠️ [N]):
- [List of neutral findings]

**Negative Impacts** (❌ [N]):
- [FIND-ZZZ]: [Brief description of negative impact and why it increases cognitive load]

**Net Assessment**:
[Paragraph explaining overall impact on data engineer experience, cognitive load, workflow]

---

### Platform Engineers

[Same structure]

---

### DevOps Engineers / SREs

[Same structure]

---

### Security Engineers

[Same structure]

---

## Recommendations (Prioritized)

### High Priority (Address Before PR Merge)

1. **[CRIT-001]**: [Recommendation title]
   - **Action**: [Specific steps to fix]
   - **Reference**: [Link to doc with correct pattern]
   - **Impact**: [What improves when fixed]

2. **[HIGH-002]**: [Recommendation title]
   [...]

### Medium Priority (Address Soon)

3. **[MED-003]**: [Recommendation title]
   [...]

### Low Priority (Consider for Future)

[...]

---

## Documentation Review Findings

[If any findings suggest documentation is outdated or contradicts best practices]

### [DOC-001] [Documentation Title] May Be Outdated

**Document**: `docs/xyz.md`
**Pattern**: [Current documented pattern]
**Research**: [Summary of WebSearch findings showing different best practice]

**Details**:
[Explanation with web search references]

**Recommendation**:
Review and consider updating documentation to align with current (2026) industry standards.

**References**:
- [Link 1 from research]
- [Link 2 from research]

---

## Positive Findings

[If any changes represent valuable patterns or improvements]

### [POS-001] [Positive Finding Title]

**Location**: `path/to/file.py`
**Pattern**: [New pattern introduced]

**Why This is Good**:
[Explanation of value]

**Recommendation**:
Consider documenting this pattern in [appropriate doc] for future reference.

---

## Change Statistics

**Files Changed**: [N] (+[additions], -[deletions] lines)

**By Package**:
- floe-core: [N] files
- floe-dagster: [N] files
- floe-dbt: [N] files
- [etc.]

**By Layer**:
- Layer 1 (Foundation): [N] files
- Layer 2 (Configuration): [N] files
- Layer 3 (Services): [N] files
- Layer 4 (Data): [N] files

**By Type**:
- Python: [N] files
- SQL: [N] files
- YAML: [N] files
- Markdown: [N] files

---

*Generated by `/arch-review` command*
*Report ID*: arch-review-YYYYMMDD-HHMMSS
*Command Version*: 1.0.0
```

---

## Key Principles (Reminder)

1. **Three-Way Validation**: Code vs docs, docs vs best practices, code vs current patterns
2. **AI-Powered Adaptive Analysis**: Use all research tools (Explore, Grep, Read, WebSearch)
3. **Living Documentation**: Documentation can become outdated - report when it does
4. **Advisory Mode**: Report findings, don't block (architecture still evolving)
5. **Escape Hatches**: Respect justified violations (`# arch-review: ignore CODE - reason`)
6. **Target State Validation**: Compare against target architecture in `docs/`, BUT challenge docs when appropriate
7. **Actionable Recommendations**: Every finding must have a clear, actionable fix

---

## Notes

- This is a **second-level review** - assume AI developers focused on pragmatic solutions, your role is architectural alignment
- Be **comprehensive but concise** - developers should scan the report in < 5 minutes
- Always **cite documentation sources** - help developers learn the architecture
- Use **WebSearch to validate** - our docs may be outdated, industry evolves
- **Think critically** - sometimes deviations are improvements, document them

---

**End of Command**
