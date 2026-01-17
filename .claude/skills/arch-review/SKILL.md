---
name: arch-review
description: Second-level architectural review validating alignment to target architecture (docs/)
---

## User Input

```text
$ARGUMENTS
```

You MUST consider the user input before proceeding (if not empty).

## Architectural Review Skill

You are conducting a **second-level architectural review** to validate that feature branch changes align with floe-runtime's **target architecture** (documented in `docs/`) and prevent known anti-patterns.

**Your Role**: Act as a guard rail against tech debt from pragmatic AI solutions while enabling refactoring toward target state.

## Memory Integration

### Before Starting
Search for prior architecture findings:
```bash
./scripts/memory-search "architecture review findings for {component}"
```

### After Completion
Save compliance findings:
```bash
./scripts/memory-save --decisions "Arch review: {key findings and decisions}" --issues "{LinearIDs}"
```

## Constitution Alignment

This skill is the enforcement mechanism for project constitution and architecture principles.

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

Categorize changes by:
- **Package**: floe-core, floe-dagster, floe-dbt, floe-iceberg, floe-polaris, floe-cube, floe-cli
- **Layer**: Layer 1 (foundation), Layer 2 (configuration), Layer 3 (services), Layer 4 (data)
- **File type**: Python (.py), SQL (.sql), YAML (.yaml/.yml), Markdown (.md), Config (.toml)

## Step 3: Research and Validate (Adaptive Analysis)

**IMPORTANT**: You have flexibility to research beyond just checking against docs. Use all available tools to provide comprehensive architectural review.

### 3a. Research Code Patterns

Use Explore, Grep, and Read tools to understand existing patterns:
- How is this pattern currently implemented elsewhere in the codebase?
- Are there existing examples of the correct approach?
- What similar changes have been made previously?
- Are there inconsistencies?

### 3b. Validate Against Documentation

Compare changes against architectural principles extracted from docs. **These are examples - read the docs for the complete list**:

**Four-Layer Architecture** (`docs/four-layer-overview.md`):
- Does Layer 4 (data) modify Layer 2 (configuration)? CRITICAL (breaks immutability)
- Do packages have upward imports (Layer 1 importing Layer 2)? CRITICAL (circular dependency)
- Does configuration flow upward instead of downward? CRITICAL (violates core invariant)

**Technology Ownership** (`CLAUDE.md`):
- Is SQL parsed in Python (outside floe-dbt)? CRITICAL ("dbt owns SQL" principle)
- Are hardcoded S3 paths in dbt models? HIGH (platform resolves storage)
- Is SQL executed in Dagster assets? CRITICAL (use dbt instead)

**Contract Compliance** (`.claude/rules/pydantic-contracts.md`):
- Is FloeSpec passed between packages (instead of CompiledArtifacts)? CRITICAL (violates contract)
- Are packages importing from each other (except CompiledArtifacts)? HIGH (breaks isolation)
- Do models use Pydantic v1 syntax? MEDIUM (use v2)

**Security** (`.claude/rules/security.md`):
- Are secrets hardcoded (passwords, API keys, tokens)? CRITICAL (security breach)
- Is dangerous code used on untrusted data? CRITICAL (injection risk)

**Testing Standards** (`.claude/rules/testing-standards.md`):
- Are tests skipped? HIGH (hidden failures)
- Is time.sleep() used in tests? MEDIUM (use wait_for_condition)
- Are tests missing requirement markers? MEDIUM (no traceability)

### 3c. Validate Against Industry Best Practices (WebSearch)

Use WebSearch to validate that documented patterns are still current best practices.

For significant architectural patterns, search for current best practices and anti-patterns.

### 3d. Think Critically

**Do not just validate "does code match docs"**. Also consider:

1. **Is our documented pattern still optimal?** Technology and practices evolve.

2. **Does the change improve architecture even if it deviates from docs?** Sometimes innovation is valuable.

3. **Are there patterns in the change that we should document?** New best practices to capture.

### 3e. Check for Escape Hatches

Respect `# arch-review: ignore CODE - reason` comments in code.

## Step 4: Assess Persona Impact

For each finding, analyze impact on the four key personas:

**Data Engineers** (Primary Persona):
- Cognitive Load, DX, Clarity, Workflow

**Platform Engineers**:
- Consistency, Governance, Immutability, Multi-env

**DevOps Engineers / SREs**:
- K8s-native, Observability, Declarative, Reliability

**Security Engineers**:
- Credentials, Secrets, Injection, Validation

## Step 5: Generate Reports

### Terminal Summary (Concise)

Output a concise terminal summary with severity counts, top recommendations, and persona impact scores.

### Markdown Report (Detailed)

Save a detailed markdown report to `.claude/reviews/arch-review-YYYYMMDD-HHMMSS.md` with:
- Executive Summary
- Architectural Alignment Score
- Findings by Severity
- Persona Impact Analysis
- Recommendations (Prioritized)
- Documentation Review Findings
- Positive Findings
- Change Statistics

## Key Principles

1. **Three-Way Validation**: Code vs docs, docs vs best practices, code vs current patterns
2. **AI-Powered Adaptive Analysis**: Use all research tools (Explore, Grep, Read, WebSearch)
3. **Living Documentation**: Documentation can become outdated - report when it does
4. **Advisory Mode**: Report findings, do not block (architecture still evolving)
5. **Escape Hatches**: Respect justified violations
6. **Target State Validation**: Compare against target architecture in `docs/`, BUT challenge docs when appropriate
7. **Actionable Recommendations**: Every finding must have a clear, actionable fix

## Handoff

After completing this skill:
- **Fix issues**: Address CRITICAL/HIGH findings
- **Create PR**: Run `/speckit.pr` when findings are addressed

## References

- **`docs/architecture/`** - Architecture documentation
- **`CLAUDE.md`** - Development guide
- **`.claude/rules/`** - Development rules
