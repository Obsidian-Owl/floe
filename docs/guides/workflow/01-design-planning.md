# Phase A: Design & Planning

Collaborative human-AI partnership for feature specification and technical design.

## Overview

Phase A ensures alignment between human intent and AI implementation before any code is written. Every major decision point uses `AskUserQuestion` for explicit confirmation.

## Workflow

```
Human provides feature description
        |
        v
/speckit.specify
        |
        +---> AskUserQuestion: Clarify requirements (up to 3)
        |
        v
/speckit.clarify (optional)
        |
        +---> AskUserQuestion: Resolve ambiguities (up to 5)
        |
        v
/speckit.plan
        |
        +---> Constitution Gate 1: MUST PASS
        +---> AskUserQuestion: Validate technical approach
        +---> Constitution Gate 2: MUST PASS
        |
        v
/speckit.analyze (optional)
        |
        +---> AskUserQuestion: Review inconsistencies
        |
        v
/speckit.tasks
        |
        +---> AskUserQuestion: Validate task granularity
        |
        v
/speckit.taskstolinear
        |
        v
Human confirms: "Ready for automated implementation"
```

## Commands

### /speckit.specify

Creates a structured feature specification from natural language.

**Input**: Feature description from user
**Output**: `specs/[epic]/spec.md` + `checklists/requirements.md`

**Process**:
1. Identify Epic ID from `docs/plans/EPIC-OVERVIEW.md`
2. Generate user scenarios (P1, P2, P3 priorities)
3. Define functional requirements (FR-001, FR-002, etc.)
4. Define key entities (if data-involved)
5. Define success criteria (measurable, technology-agnostic)
6. Ask up to 3 clarification questions via `AskUserQuestion`

### /speckit.clarify

Reduces specification ambiguity through targeted questions.

**Input**: Existing `spec.md`
**Output**: Updated `spec.md` with clarifications section

**Question Categories**:
- Functional Scope & Behavior
- Domain & Data Model
- Interaction & UX Flow
- Non-Functional Quality Attributes
- Integration & External Dependencies
- Edge Cases & Failure Handling

**Rules**:
- Maximum 5 questions per session
- Each question must be answerable (multiple-choice or <=5 words)
- Atomic file writes (save after each clarification)

### /speckit.plan

Develops technical architecture with constitution gates.

**Input**: `spec.md` + optional clarifications
**Output**: `plan.md`, `research.md`, `data-model.md`, `contracts/`

**Phases**:

**Phase 0: Research & Unknowns**
- Fill technical context (language, dependencies, storage, etc.)
- Mark unknowns as "NEEDS CLARIFICATION"
- **Constitution Gate 1** (MUST PASS before Phase 1)

**Phase 1: Design & Contracts**
- Extract entities from spec to `data-model.md`
- Generate API contracts to `contracts/`
- **Constitution Gate 2** (MUST PASS before handoff)

**Constitution Check Categories**:
1. Technology Ownership (dbt owns SQL)
2. Plugin-First Architecture
3. Enforced vs Pluggable
4. Contract-Driven Integration
5. K8s-Native Testing
6. Security First
7. Four-Layer Architecture
8. Observability By Default

### /speckit.tasks

Decomposes the plan into granular, independently testable tasks.

**Input**: `plan.md` + `spec.md` + design artifacts
**Output**: `tasks.md` with T### IDs, phases, dependencies

**Task Format**:
```
- [ ] T001 Create project structure per implementation plan
- [ ] T005 [P] Implement authentication middleware in src/middleware/auth.py
- [ ] T012 [P] [US1] Create User model in src/models/user.py
- [ ] T014 [US1] Implement UserService (depends on T012, T013)
```

**Markers**:
- `[P]` - Can run in parallel (no file overlap)
- `[US#]` - User story association
- `(depends on T###)` - Explicit dependency

**Phases**:
1. Setup (project initialization)
2. Foundational (blocking prerequisites)
3. User Stories (P1, P2, P3... in priority order)
4. Polish & Cross-Cutting Concerns

### /speckit.taskstolinear

Creates Linear issues and establishes bidirectional sync.

**Input**: `tasks.md`
**Output**: Linear issues + `.linear-mapping.json`

**Process**:
1. Query Linear Project (must exist: `floe-{NN}-{slug}`)
2. Create/find Epic label (`epic:01`, `epic:10a`)
3. Create Linear issues with structured descriptions
4. Set up blockedBy dependencies
5. Generate mapping file for traceability

## Artifacts

| File | Purpose |
|------|---------|
| `spec.md` | Feature specification |
| `checklists/requirements.md` | Spec quality checklist |
| `plan.md` | Technical implementation plan |
| `research.md` | Phase 0 research findings |
| `data-model.md` | Entity definitions |
| `contracts/` | API contracts (OpenAPI, GraphQL) |
| `tasks.md` | Task breakdown with T### IDs |
| `.linear-mapping.json` | Task to Linear ID mapping |

## Human Checkpoints

| Checkpoint | When | Purpose |
|------------|------|---------|
| Spec clarifications | After /speckit.specify | Validate requirements understanding |
| Ambiguity resolution | During /speckit.clarify | Reduce downstream rework |
| Technical approach | After /speckit.plan | Approve architecture decisions |
| Task granularity | After /speckit.tasks | Ensure independent testability |
| Ready for automation | After /speckit.taskstolinear | Confirm Linear issues correct |

## Best Practices

1. **Be specific in feature descriptions** - More context reduces clarification rounds
2. **Review constitution gates carefully** - Violations caught here save rework
3. **Validate task dependencies** - Incorrect dependencies block parallelization
4. **Confirm Linear project exists** - Create in Linear UI before /speckit.taskstolinear
5. **Check .linear-mapping.json** - Ensures traceability works correctly

## Next Step

After Phase A completes successfully:
```
User confirms: "Ready for automated implementation"
```

Proceed to [Phase B: Automated Implementation](02-automated-implementation.md)
