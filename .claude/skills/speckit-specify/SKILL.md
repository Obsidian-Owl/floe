---
name: speckit-specify
description: Create or update the feature specification from a natural language feature description.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Memory Integration

### Before Starting
Search for related prior work:
```bash
./scripts/memory-search "{feature keywords}"
```

Look for: existing patterns, prior decisions, related features.
Use findings to inform scope and avoid contradicting prior decisions.

### After Completion
Save key requirements captured:
```bash
./scripts/memory-save --decisions "Key requirements for {feature}: {summary}" --issues ""
```

## Constitution Alignment

This skill aligns with project principles:
- **User-Focused**: Specifications focus on WHAT users need, not HOW to implement
- **Testable Requirements**: Every requirement must be verifiable
- **Clear Boundaries**: Explicit scope and out-of-scope declarations

## Outline

The text the user typed after `/speckit.specify` in the triggering message **is** the feature description. Assume you always have it available in this conversation even if `$ARGUMENTS` appears literally below. Do not ask the user to repeat it unless they provided an empty command.

Given that feature description, do this:

1. **Query Agent-Memory for Related Context** (if available):
   - Search for prior work related to this feature domain:
     ```bash
     ./scripts/memory-search "{feature keywords}"
     ```
   - Look for: existing patterns, prior decisions, related features
   - Use findings to inform scope and avoid contradicting prior decisions
   - If agent-memory unavailable, continue without (non-blocking)

2. **Identify the Epic this feature belongs to**:

   All features MUST be associated with an Epic from the project's Epic Overview.

   **How to find the Epic ID**:
   - Read `docs/plans/EPIC-OVERVIEW.md` to see the full list of Epics and their IDs
   - Epic IDs follow the pattern: number + optional letter (e.g., 1, 2A, 2B, 3A, 9C)
   - Match the feature description to an Epic name/purpose in that document

   **How to determine the Epic**:
   - If the user explicitly mentions an Epic (e.g., "for Epic 2A" or "part of the Manifest Schema epic"), use that
   - If unclear from the feature description, use the AskUserQuestion tool to ask which Epic this belongs to
   - Provide suggested options based on the Epic names in EPIC-OVERVIEW.md

3. **Generate a concise short name** (2-4 words) for the branch:
   - Analyze the feature description and extract the most meaningful keywords
   - Create a 2-4 word short name that captures the essence of the feature
   - Use action-noun format when possible (e.g., "manifest-validation", "plugin-discovery")
   - Preserve technical terms and acronyms (OAuth2, API, JWT, etc.)
   - Keep it concise but descriptive enough to understand the feature at a glance

4. **Check for existing specs for this Epic**:

   a. First, fetch all remote branches to ensure we have the latest information:

      ```bash
      git fetch --all --prune
      ```

   b. Check if specs already exist for this Epic:
      - Remote branches: `git ls-remote --heads origin | grep -iE 'refs/heads/<epic-id>-'` (e.g., `2a-`, `9c-`)
      - Local branches: `git branch | grep -iE '^[* ]*<epic-id>-'`
      - Specs directories: Check for directories matching `specs/<epic-id>-*`

   c. Determine if this is a new feature or continuation:
      - If an existing spec matches this Epic + short-name, warn the user and ask if they want to continue work on it
      - If no existing spec, proceed with creating a new one

   d. Run the script `.specify/scripts/bash/create-new-feature.sh --json "$ARGUMENTS"` with the Epic ID and short-name:
      - Pass `--epic <epic-id>` and `--short-name "your-short-name"` along with the feature description
      - Bash example: `.specify/scripts/bash/create-new-feature.sh --json --epic 2a --short-name "manifest-validation" "Implement manifest schema validation"`
      - The Epic ID should be lowercase (e.g., `2a` not `2A`, `9c` not `9C`)

   **IMPORTANT**:
   - Every feature MUST have a valid Epic ID (check `docs/plans/EPIC-OVERVIEW.md`)
   - Use lowercase for Epic IDs in branch names (2a, 9c, not 2A, 9C)
   - You must only ever run this script once per feature
   - The JSON is provided in the terminal as output - always refer to it to get the actual content you're looking for
   - The JSON output will contain BRANCH_NAME, SPEC_FILE paths, and EPIC_ID
   - For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot")

5. Load `.specify/templates/spec-template.md` to understand required sections.

6. Follow this execution flow:

    1. Parse user description from Input
       If empty: ERROR "No feature description provided"
    2. Extract key concepts from description
       Identify: actors, actions, data, constraints
    3. For unclear aspects:
       - Clarify by using the AskUserQuestions Tool
    4. Fill User Scenarios & Testing section
       If no clear user flow: ERROR "Cannot determine user scenarios"
    5. Generate Functional Requirements
       Each requirement must be testable
       Use reasonable defaults for unspecified details (document assumptions in Assumptions section)
    6. Define Success Criteria
       Create measurable, technology-agnostic outcomes
       Include both quantitative metrics (time, performance, volume) and qualitative measures (user satisfaction, task completion)
       Each criterion must be verifiable without implementation details
    7. Identify Key Entities (if data involved)
    8. Return: SUCCESS (spec ready for planning)

7. Write the specification to SPEC_FILE using the template structure, replacing placeholders with concrete details derived from the feature description (arguments) while preserving section order and headings.

8. **Specification Quality Validation**: After writing the initial spec, validate it against quality criteria:

   a. **Create Spec Quality Checklist**: Generate a checklist file at `FEATURE_DIR/checklists/requirements.md` using the checklist template structure with validation items

   b. **Run Validation Check**: Review the spec against each checklist item:
      - For each item, determine if it passes or fails
      - Document specific issues found (quote relevant spec sections)

   c. **Handle Validation Results**:

      - **If all items pass**: Mark checklist complete and proceed to step 8

      - **If items fail (excluding [NEEDS CLARIFICATION])**:
        1. List the failing items and specific issues
        2. Update the spec to address each issue
        3. Re-run validation until all items pass (max 3 iterations)
        4. If still failing after 3 iterations, document remaining issues in checklist notes and warn user

      - **If [NEEDS CLARIFICATION] markers remain**:
        1. Extract all [NEEDS CLARIFICATION: ...] markers from the spec
        2. **LIMIT CHECK**: If more than 3 markers exist, keep only the 3 most critical (by scope/security/UX impact) and make informed guesses for the rest
        3. For each clarification needed (max 3), present options to user
        4. Wait for user to respond with their choices for all questions
        5. Update the spec by replacing each [NEEDS CLARIFICATION] marker with the user's selected or provided answer
        6. Re-run validation after all clarifications are resolved

   d. **Update Checklist**: After each validation iteration, update the checklist file with current pass/fail status

9. Report completion with branch name, spec file path, checklist results, Epic ID, and readiness for the next phase (`/speckit.clarify` or `/speckit.plan`).

**NOTE:** The script creates and checks out the new branch and initializes the spec file before writing.

## General Guidelines

### Quick Guidelines

- Focus on **WHAT** users need and **WHY**.
- Avoid HOW to implement (no tech stack, APIs, code structure).
- Written for business stakeholders, not developers.
- DO NOT create any checklists that are embedded in the spec. That will be a separate command.

### Section Requirements

- **Mandatory sections**: Must be completed for every feature
- **Optional sections**: Include only when relevant to the feature
- When a section doesn't apply, remove it entirely (don't leave as "N/A")

### For AI Generation

When creating this spec from a user prompt:

1. **Don't guess**: Use the AskUserQuestions tool to validate reasoning
2. **Document assumptions**: Record reasonable defaults in the Assumptions section
3. **Limit clarifications**: Maximum 3 [NEEDS CLARIFICATION] markers - use only for critical decisions
4. **Prioritize clarifications**: scope > security/privacy > user experience > technical details
5. **Think like a tester**: Every vague requirement should fail the "testable and unambiguous" checklist item

### Success Criteria Guidelines

Success criteria must be:

1. **Measurable**: Include specific metrics (time, percentage, count, rate)
2. **Technology-agnostic**: No mention of frameworks, languages, databases, or tools
3. **User-focused**: Describe outcomes from user/business perspective, not system internals
4. **Verifiable**: Can be tested/validated without knowing implementation details

## Handoff

After completing this skill:
- **Clarify requirements**: Run `/speckit.clarify` to resolve ambiguities
- **Create plan**: Run `/speckit.plan` to generate technical implementation plan

## References

- **`.specify/templates/spec-template.md`** - Specification template
- **`docs/plans/EPIC-OVERVIEW.md`** - Epic definitions
- **`.specify/memory/constitution.md`** - Project principles
