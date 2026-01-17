---
name: speckit-checklist
description: Generate a custom checklist for the current feature based on user requirements.
---

## Checklist Purpose: "Unit Tests for English"

**CRITICAL CONCEPT**: Checklists are **UNIT TESTS FOR REQUIREMENTS WRITING** - they validate the quality, clarity, and completeness of requirements in a given domain.

**NOT for verification/testing**:
- NOT "Verify the button clicks correctly"
- NOT "Test error handling works"
- NOT "Confirm the API returns 200"
- NOT checking if code/implementation matches the spec

**FOR requirements quality validation**:
- "Are visual hierarchy requirements defined for all card types?" (completeness)
- "Is 'prominent display' quantified with specific sizing/positioning?" (clarity)
- "Are hover state requirements consistent across all interactive elements?" (consistency)
- "Are accessibility requirements defined for keyboard navigation?" (coverage)
- "Does the spec define what happens when logo image fails to load?" (edge cases)

**Metaphor**: If your spec is code written in English, the checklist is its unit test suite. You're testing whether the requirements are well-written, complete, unambiguous, and ready for implementation - NOT whether the implementation works.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Memory Integration

This skill generates quality validation artifacts - no memory search/save needed.

## Constitution Alignment

This skill enforces project principles:
- **Testable Requirements**: Every requirement must be verifiable
- **Traceability**: Checklist items link back to spec sections

## Execution Steps

1. **Setup**: Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse JSON for FEATURE_DIR and AVAILABLE_DOCS list.
   - All file paths must be absolute.

2. **Clarify intent (dynamic)**: Derive up to THREE initial contextual clarifying questions (no pre-baked catalog). They MUST:
   - Be generated from the user's phrasing + extracted signals from spec/plan/tasks
   - Only ask about information that materially changes checklist content
   - Be skipped individually if already unambiguous in `$ARGUMENTS`
   - Prefer precision over breadth

3. **Understand user request**: Combine `$ARGUMENTS` + clarifying answers:
   - Derive checklist theme (e.g., security, review, deploy, ux)
   - Consolidate explicit must-have items mentioned by user
   - Map focus selections to category scaffolding
   - Infer any missing context from spec/plan/tasks (do NOT hallucinate)

4. **Load feature context**: Read from FEATURE_DIR:
   - spec.md: Feature requirements and scope
   - plan.md (if exists): Technical details, dependencies
   - tasks.md (if exists): Implementation tasks

5. **Generate checklist** - Create "Unit Tests for Requirements":
   - Create `FEATURE_DIR/checklists/` directory if it doesn't exist
   - Generate unique checklist filename:
     - Use short, descriptive name based on domain (e.g., `ux.md`, `api.md`, `security.md`)
     - Format: `[domain].md`
     - If file exists, append to existing file
   - Number items sequentially starting from CHK001
   - Each `/speckit.checklist` run creates a NEW file (never overwrites existing checklists)

   **CORE PRINCIPLE - Test the Requirements, Not the Implementation**:
   Every checklist item MUST evaluate the REQUIREMENTS THEMSELVES for:
   - **Completeness**: Are all necessary requirements present?
   - **Clarity**: Are requirements unambiguous and specific?
   - **Consistency**: Do requirements align with each other?
   - **Measurability**: Can requirements be objectively verified?
   - **Coverage**: Are all scenarios/edge cases addressed?

   **Category Structure** - Group items by requirement quality dimensions:
   - Requirement Completeness
   - Requirement Clarity
   - Requirement Consistency
   - Acceptance Criteria Quality
   - Scenario Coverage
   - Edge Case Coverage
   - Non-Functional Requirements
   - Dependencies & Assumptions
   - Ambiguities & Conflicts

   **REQUIRED PATTERNS**:
   - "Are [requirement type] defined/specified/documented for [scenario]?"
   - "Is [vague term] quantified/clarified with specific criteria?"
   - "Are requirements consistent between [section A] and [section B]?"
   - "Can [requirement] be objectively measured/verified?"
   - "Are [edge cases/scenarios] addressed in requirements?"
   - "Does the spec define [missing aspect]?"

   **ABSOLUTELY PROHIBITED**:
   - Any item starting with "Verify", "Test", "Confirm", "Check" + implementation behavior
   - References to code execution, user actions, system behavior
   - "Displays correctly", "works properly", "functions as expected"
   - "Click", "navigate", "render", "load", "execute"

   **Traceability Requirements**:
   - MINIMUM: >=80% of items MUST include at least one traceability reference
   - Each item should reference: spec section `[Spec section X.Y]`, or use markers: `[Gap]`, `[Ambiguity]`, `[Conflict]`, `[Assumption]`

6. **Structure Reference**: Generate the checklist following the canonical template in `.specify/templates/checklist-template.md` for title, meta section, category headings, and ID formatting.

7. **Report**: Output full path to created checklist, item count, and remind user that each run creates a new file. Summarize:
   - Focus areas selected
   - Depth level
   - Actor/timing
   - Any explicit user-specified must-have items incorporated

## Example Checklist Types & Sample Items

**UX Requirements Quality:** `ux.md`
- "Are visual hierarchy requirements defined with measurable criteria? [Clarity, Spec section FR-1]"
- "Is the number and positioning of UI elements explicitly specified? [Completeness, Spec section FR-1]"
- "Are interaction state requirements (hover, focus, active) consistently defined? [Consistency]"

**API Requirements Quality:** `api.md`
- "Are error response formats specified for all failure scenarios? [Completeness]"
- "Are rate limiting requirements quantified with specific thresholds? [Clarity]"
- "Are authentication requirements consistent across all endpoints? [Consistency]"

**Security Requirements Quality:** `security.md`
- "Are authentication requirements specified for all protected resources? [Coverage]"
- "Are data protection requirements defined for sensitive information? [Completeness]"
- "Is the threat model documented and requirements aligned to it? [Traceability]"

## Handoff

After completing this skill:
- **Review checklist**: Manually review generated checklist items
- **Update spec**: Run `/speckit.clarify` if gaps identified

## References

- **`.specify/templates/checklist-template.md`** - Checklist template
- **`spec.md`** - Feature specification
