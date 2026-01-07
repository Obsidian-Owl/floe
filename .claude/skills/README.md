# Skills Index

This directory contains research-driven Skills for component SDK development.

## Philosophy

Skills do NOT prescribe specific patterns. Instead, they:
1. **Research** the current SDK version and capabilities
2. **Discover** existing patterns in the codebase
3. **Validate** implementations against SDK documentation
4. **Verify** integration with other components

Each skill follows the **progressive disclosure** pattern - injecting context only as needed.

## Available Skills

### Infrastructure & Deployment

#### [helm-k8s-deployment](helm-k8s-skill/SKILL.md)
**Use when**: Working with Helm charts, K8s deployments, debugging pods, or analysing container logs

**Capabilities**:
- Context-efficient log analysis (never dumps full logs)
- Helm chart validation and templating
- K8s debugging with targeted extraction
- Subagent delegation for deep analysis

**Key Resources**:
- [SKILL.md](helm-k8s-skill/SKILL.md) - Context-preserving K8s debugging

---

### Data Validation & Type Safety

#### [pydantic-schemas](pydantic-skill/SKILL.md)
**Use when**: Working with data models, configuration, validation, or API contracts

**Capabilities**:
- Pydantic v2 syntax validation
- Field and model validators
- ConfigDict configuration
- SecretStr for sensitive data
- JSON schema export

**Key Resources**:
- [SKILL.md](pydantic-skill/SKILL.md) - Research protocol and validation workflow
- [API-REFERENCE.md](pydantic-skill/API-REFERENCE.md) - Pydantic v2 API changes

---

### Orchestration & Execution

#### [dagster-orchestration](dagster-skill/SKILL.md)
**Use when**: Building data orchestration, pipeline execution, or asset management

**Capabilities**:
- Software-defined assets
- Resources and IO managers
- Schedules and sensors
- dbt integration (dagster-dbt)
- Metadata and observability

**Key Resources**:
- [SKILL.md](dagster-skill/SKILL.md) - Asset patterns and integration points
- [API-REFERENCE.md](dagster-skill/API-REFERENCE.md) - Dagster API reference

---

#### [dbt-transformations](dbt-skill/SKILL.md)
**Use when**: Building SQL transformations, data quality tests, or dbt project configuration

**Capabilities**:
- dbt models (SQL and Python)
- Tests and snapshots
- Macros and sources
- Programmatic invocation (dbtRunner)
- **CRITICAL**: dbt owns SQL - never parse SQL in Python

**Key Resources**:
- [SKILL.md](dbt-skill/SKILL.md) - dbt development workflow and integration

---

### Storage & Catalog

#### [pyiceberg-storage](pyiceberg-skill/SKILL.md)
**Use when**: Working with Iceberg table storage, time-travel queries, or data lake operations

**Capabilities**:
- Table operations (create, load, scan)
- ACID transactions
- Schema evolution
- Partitioning and time travel
- Catalog integration (Polaris)

**Key Resources**:
- [SKILL.md](pyiceberg-skill/SKILL.md) - PyIceberg operations and patterns

---

#### [polaris-catalog](polaris-skill/SKILL.md)
**Use when**: Working with Iceberg catalog management, metadata organization, or access governance

**Capabilities**:
- Catalog management
- Namespace organization
- Principal and role management
- Access control
- REST API integration

**Key Resources**:
- [SKILL.md](polaris-skill/SKILL.md) - Polaris catalog operations

---

### Consumption Layer

#### [cube-semantic-layer](cube-skill/SKILL.md)
**Use when**: Building semantic layer, consumption APIs, or metrics layer on top of dbt models

**Capabilities**:
- dbt integration (cube_dbt package)
- Measures and dimensions
- Pre-aggregations
- REST API queries
- Data modeling

**Key Resources**:
- [SKILL.md](cube-skill/SKILL.md) - Cube semantic layer development

---

## How Skills Work

### Research Protocol (4 Steps)

Every skill follows this protocol:

1. **Verify Runtime Environment**
   ```bash
   python -c "import <package>; print(<package>.__version__)"
   ```

2. **Research SDK State** (if unfamiliar)
   - Use WebSearch for "<package> [feature] documentation 2025"
   - Check official documentation

3. **Discover Existing Patterns**
   ```bash
   rg "pattern" --type py
   ```

4. **Validate Against Architecture**
   - Read `/docs/` for requirements
   - Check integration points

### Context Injection (Not Prescription)

Skills inject:
- Research queries for WebSearch
- Validation steps
- Quick reference commands
- Integration checkpoints

Skills do NOT inject:
- Specific implementations
- Code patterns (unless verified from codebase)
- Assumptions about contract state

## Using Skills

### In Claude Code

Skills are automatically available. When working on a component:

```markdown
# Implicit skill invocation
"Create a Pydantic schema for FloeSpec"
→ Claude may invoke pydantic-schemas skill

# Explicit skill invocation
"Use the pydantic-schemas skill to help me design the CompiledArtifacts contract"
```

### Skill Selection Guide

| Task | Primary Skill | Secondary Skills |
|------|---------------|------------------|
| Define FloeSpec schema | pydantic-schemas | - |
| Create Dagster assets | dagster-orchestration | dbt-transformations |
| Write dbt models | dbt-transformations | - |
| Manage Iceberg tables | pyiceberg-storage | polaris-catalog |
| Configure Polaris catalog | polaris-catalog | pyiceberg-storage |
| Define semantic layer | cube-semantic-layer | dbt-transformations |
| Implement compiler | pydantic-schemas | All (integration) |

## Skill Development Guidelines

When creating new skills:

1. **Research-driven**: Verify SDK state before documenting
2. **Context-injecting**: Provide research steps, not implementations
3. **Progressive disclosure**: Load context only as needed
4. **Version-agnostic**: Guide discovery of current version capabilities
5. **Integration-aware**: Reference other skills and architecture docs

### Skill Template

```markdown
---
name: skill-name
description: Research-driven [purpose]. Injects research steps for [features].
allowed-tools: Read, Grep, Glob, Bash, WebSearch
---

# [Component] Development (Research-Driven)

## Philosophy

This skill does NOT prescribe specific patterns. Instead, it guides you to:
1. **Research** the current [SDK] version and capabilities
2. **Discover** existing patterns in the codebase
3. **Validate** your implementations against [SDK] documentation
4. **Verify** integration with [other components]

## Pre-Implementation Research Protocol

### Step 1: Verify Runtime Environment
...

### Step 2: Research SDK State
...

### Step 3: Discover Existing Patterns
...

### Step 4: Validate Against Architecture
...

## Implementation Guidance (Not Prescriptive)
...

## Context Injection (For Future Claude Instances)
...

## Quick Reference: Common Research Queries
...
```

## Updating Skills

Skills evolve as SDKs evolve. To update:

1. **Research latest SDK version**:
   ```bash
   pip list --outdated | grep <package>
   ```

2. **Update API-REFERENCE.md** with new features

3. **Add new research queries** to Quick Reference section

4. **Test skill guidance** by using it to implement a feature

5. **Keep it research-driven** - don't prescribe patterns

## Integration with Architecture Docs

Skills reference architecture docs for requirements:

- [00-overview.md](../../docs/00-overview.md) - System overview
- [01-constraints.md](../../docs/01-constraints.md) - Technical constraints
- [03-solution-strategy.md](../../docs/03-solution-strategy.md) - Solution approach
- [04-building-blocks.md](../../docs/04-building-blocks.md) - CompiledArtifacts contract
- [10-glossary.md](../../docs/10-glossary.md) - Terminology

## Summary

✅ **6 Skills** covering all major components
✅ **Research-driven** - discover, don't invent
✅ **Context-injecting** - guide, don't prescribe
✅ **Version-agnostic** - verify runtime state
✅ **Integration-aware** - reference architecture docs

This enables rapid, accurate development while maintaining architectural integrity.
