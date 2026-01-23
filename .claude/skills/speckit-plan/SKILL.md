---
name: speckit-plan
description: Execute the implementation planning workflow using the plan template to generate design artifacts.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Memory Integration

### Before Starting
Search for prior architecture decisions:
```bash
./scripts/memory-search "architecture decisions for {feature_domain}"
```

Look for: prior technology choices, rejected alternatives, lessons learned.
Document any relevant findings in research.md under "Prior Decisions" section.

### After Completion
Save key decisions for future sessions:
```bash
./scripts/memory-save --decisions "Chose {technology} for {purpose}; Rejected {alternative} because {reason}" --issues "{Linear issue IDs}"
```

What to save:
- Technology choices made
- Alternatives that were rejected (and why)
- Architecture patterns selected

## Constitution Alignment

This skill enforces project principles:
- **Technology Ownership**: Respect boundaries (dbt owns SQL, Dagster owns orchestration)
- **Contract-Driven**: CompiledArtifacts is the sole integration contract
- **K8s-Native**: All designs must be Kubernetes-native

## Integration Design (REQUIRED)

Every plan.md MUST include an Integration Design section. This ensures features are designed to connect to the system, not operate in isolation.

**Add to plan.md after Technical Context:**

```markdown
## Integration Design

### Entry Point Integration
- [ ] Feature reachable from: [CLI / Plugin / API / Internal]
- [ ] Integration point: [specific file/module that exposes this]
- [ ] Wiring task needed: [Yes/No - if Yes, add to tasks.md]

### Dependency Integration
| This Feature Uses | From Package | Integration Point |
|-------------------|--------------|-------------------|
| CompiledArtifacts | floe-core | Loaded via .from_json_file() |
| [component] | [package] | [how integrated] |

### Produces for Others
| Output | Consumers | Contract |
|--------|-----------|----------|
| [schema/API/plugin] | [who uses it] | [Pydantic model/entry point] |

### Cleanup Required (if refactoring)
If this feature replaces or refactors existing code:
- [ ] Old code to remove: [files/functions to delete]
- [ ] Old tests to remove: [test files that test removed code]
- [ ] Old docs to update: [docs referencing old code]
```

**Key Questions to Answer:**
1. Can a user reach this feature from `floe` CLI or plugin loading?
2. If this creates schemas, are they added to CompiledArtifacts or exported?
3. If this replaces code, what gets deleted?

**If integration is unclear**: Research existing patterns in `docs/architecture/` before designing.

## Outline

1. **Setup**: Run `.specify/scripts/bash/setup-plan.sh --json` from repo root and parse JSON for FEATURE_SPEC, IMPL_PLAN, SPECS_DIR, BRANCH. For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").

2. **Query Agent-Memory for Prior Context** (if available):
   - Search for prior decisions related to this feature domain:
     ```bash
     ./scripts/memory-search "architecture decisions for {feature_domain}"
     ```
   - Look for: prior technology choices, rejected alternatives, lessons learned
   - Document any relevant findings in research.md under "Prior Decisions" section
   - If agent-memory unavailable, continue without (non-blocking)

3. **Load context**: Read FEATURE_SPEC and `.specify/memory/constitution.md`. Load IMPL_PLAN template (already copied).

4. **Execute plan workflow**: Follow the structure in IMPL_PLAN template to:
   - Fill Technical Context (mark unknowns as "NEEDS CLARIFICATION")
   - Fill Constitution Check section from constitution
   - Evaluate gates (ERROR if violations unjustified)
   - Phase 0: Generate research.md (resolve all NEEDS CLARIFICATION)
   - Phase 1: Generate data-model.md, contracts/, quickstart.md
   - Phase 1: Update agent context by running the agent script
   - Re-evaluate Constitution Check post-design

5. **Stop and report**: Command ends after Phase 2 planning. Report branch, IMPL_PLAN path, and generated artifacts.

6. **Capture Decisions to Agent-Memory** (if available):
   - Extract key decisions from research.md and plan.md:
     - Technology choices made
     - Alternatives that were rejected (and why)
     - Architecture patterns selected
   - Save to agent-memory for future sessions:
     ```bash
     ./scripts/memory-save --decisions "Chose {technology} for {purpose}; Rejected {alternative} because {reason}" --issues "{Linear issue IDs}"
     ```
   - If agent-memory unavailable, decisions are still captured in plan artifacts (non-blocking)

## Phases

### Phase 0: Outline & Research

1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION: research task
   - For each dependency: best practices task
   - For each integration: patterns task

2. **Generate and dispatch research agents**:

   ```text
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]
   - Clarify any ambiguities or questions by using the AskUserQuestion Tool

**Output**: research.md with all NEEDS CLARIFICATION resolved

### Phase 1: Design & Contracts

**Prerequisites:** `research.md` complete

1. **Extract entities from feature spec**: `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action: endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Agent context update**:
   - Run `.specify/scripts/bash/update-agent-context.sh claude`
   - These scripts detect which AI agent is in use
   - Update the appropriate agent-specific context file
   - Add only new technology from current plan
   - Preserve manual additions between markers

**Output**: data-model.md, /contracts/*, quickstart.md, agent-specific file

## Key Rules

- Use absolute paths
- ERROR on gate failures or unresolved clarifications

## Handoff

After completing this skill:
- **Generate tasks**: Run `/speckit.tasks` to create actionable task list
- **Create checklist**: Run `/speckit.checklist` to create quality checklist

## References

- **`.specify/templates/plan-template.md`** - Plan template
- **`.specify/memory/constitution.md`** - Project principles
- **`docs/architecture/`** - Architecture documentation
