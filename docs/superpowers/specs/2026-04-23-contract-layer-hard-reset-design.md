# Contract Layer Hard Reset Design

Status: Proposed and approved in brainstorming
Date: 2026-04-23
Author: Codex

## Summary

floe is accumulating debugging cost because cross-consumer operational facts are authored in multiple places at once. Service identity, ports, env bindings, runtime enums, CLI/result payloads, and execution assumptions are currently spread across Helm templates, Python fixtures, shell scripts, runtime code, and tests. The system therefore does not have one source of truth; it has several partially-overlapping truths that drift independently.

This design introduces a generation-first contract layer inside `floe-core` and treats it as the only authoritative source for shared operational facts. Consumers such as charts, fixtures, scripts, runtime helpers, and tests become adapters over generated bindings rather than authors of their own facts.

This is a hard reset. floe has not shipped a tagged release, so the design explicitly favors deletion of legacy compatibility paths over preservation.

## Problem Statement

Recent failures show the same structural issue repeating at different boundaries:

- Runtime contract drift:
  - `AuthType.NONE` is referenced in integration tests while the runtime schema defines `AuthType.ANONYMOUS`.
- Behavioral schema drift:
  - CLI/test expectations diverge on keys like `findings` and `diffs`.
- Service identity drift:
  - Service names and network assumptions differ across charts, fixtures, and tests.
- Execution-context drift:
  - Some in-cluster tests behave like black-box deployed checks, while others expect git metadata, local files, `localhost`, or privileged Helm/secret access.
- Bootstrap coupling:
  - DevPod, Flux, direct Helm, vendored chart dependencies, and local/runtime test assumptions are too entangled, so failures are difficult to classify correctly.

The result is ambiguous red builds. A failing test may indicate:

- a real product regression
- contract drift between consumers
- bootstrap/environment failure
- execution-context mismatch
- fixture or test harness drift

This ambiguity is the core reason debugging is expensive.

## Goals

- Establish one authoritative contract system for cross-consumer operational facts.
- Remove hand-authored duplication for service identity, env bindings, runtime enums, and behavioral/result schemas.
- Make drift structurally hard by generating consumer bindings from canonical models.
- Split validation into execution classes that answer one question each.
- Favor deletion of obsolete authoring paths over compatibility shims.
- Make a red test easier to classify as contract, bootstrap, platform-behavior, or developer-workflow failure.

## Non-Goals

- Preserve backward compatibility for pre-release interfaces.
- Build a language-neutral platform for hypothetical future ecosystems.
- Keep old fixtures, scripts, or aliases alive "just in case."
- Solve every architecture concern in the repo unrelated to shared-contract drift.

## Approaches Considered

### 1. Monolithic canonical contract package

Create a single package that owns topology, env injection, runtime enums, and behavioral/result schemas in one place.

Pros:

- Strong conceptual source of truth.
- Fastest to explain.

Cons:

- High risk of becoming a god-model.
- Unnecessary coupling between unrelated domains.
- Harder to evolve safely.

### 2. Domain-bounded contract layer with generation-first adapters

Create one contract system with bounded domains, and generate consumer-specific bindings and adapters from those domains.

Pros:

- Removes duplicate authoring while keeping domains understandable.
- Matches the actual drift patterns seen in floe.
- Supports a hard reset without forcing a monolith.

Cons:

- Requires clearer boundary definition up front.
- Slightly more architecture work before implementation.

### 3. External declarative spec registry with multi-language generation

Define shared contracts in a neutral registry format and generate Python, Helm, shell, and schema outputs from it.

Pros:

- Strong long-term extensibility.
- Good fit for a future multi-language ecosystem.

Cons:

- Too much machinery for the current stage.
- Slower path to reducing current debugging cost.

## Decision

Adopt approach 2.

The target architecture is a domain-bounded, generation-first contract layer inside `floe-core`. This contract layer becomes the only permitted source for shared operational facts. Consumer code may transform or validate those facts, but it may not author competing versions.

## Target Architecture

Canonical models live under `floe_core.contracts` and are split into four domains.

### 1. `topology`

Owns shared service and deployment identity:

- canonical component IDs
- service names
- namespaces and namespace rules
- ports
- readiness/health endpoints
- connection descriptors

### 2. `execution`

Owns execution-context bindings:

- in-cluster runtime bindings
- host-based runtime bindings
- DevPod bindings
- demo runtime bindings
- env var mappings and exposure rules
- context-specific access rules

### 3. `schemas`

Owns machine-readable behavioral contracts:

- CLI JSON payloads
- status/result payloads
- artifact/result schemas
- adapter-visible machine outputs

### 4. `runtime`

Owns cross-package runtime constants and enums:

- auth modes
- shared runtime identifiers
- shared plugin/runtime contract values

## Generation Model

The contract layer is generation-first.

Canonical models produce consumer-facing artifacts such as:

- Python bindings for fixtures, test helpers, and runtime adapters
- Helm-facing values/helpers or generated binding fragments for charts
- shell/env export artifacts for scripts that still require env injection
- JSON schema artifacts or typed adapter surfaces for CLI/result contracts

The direction of truth is one-way:

1. canonical contract model
2. generated consumer binding
3. thin consumer adapter

Consumers do not define new facts if those facts are shared across more than one boundary.

## Architectural Rules

These rules are mandatory.

### Rule 1: No duplicated cross-consumer literals

If a service name, port, auth mode, schema key, readiness path, or env binding matters across multiple consumers, it must exist in the contract layer and nowhere else as an authored literal.

### Rule 2: Consumers are adapters, not authorities

Charts, scripts, fixtures, and tests may consume generated bindings, but they may not independently define the same facts.

### Rule 3: Wrong execution context must fail explicitly

Helpers may not silently fall back from in-cluster to localhost, from black-box to git-local, or from runtime to developer context. Context mismatch must produce an explicit failure.

### Rule 4: Bootstrap failures must fail before product validation

Environment availability belongs to bootstrap validation, not to downstream product tests.

## Data Flow

Facts flow downward in a single direction:

1. contract domain models are defined in `floe_core.contracts`
2. generators emit bindings for consumers
3. consumers adapt those bindings into their local runtime
4. tests validate behavior against generated contracts

This eliminates the current pattern where:

- fixtures have their own service tables
- chart templates define env binding semantics independently
- scripts invent their own env conventions
- tests encode alternate assumptions

## Validation Boundary Split

The test stack must be split into distinct execution classes.

### `contract`

Purpose:

- validate canonical models
- validate generated artifacts
- validate adapter conformance

Properties:

- fast
- deterministic
- no unnecessary cluster dependency

### `bootstrap`

Purpose:

- validate environment bring-up
- validate DevPod/Hetzner, Helm, Flux, registry, chart dependency, and platform readiness prerequisites

Properties:

- answers "is the environment usable?"
- should fail before product E2E begins

### `platform-blackbox`

Purpose:

- validate deployed system behavior from an in-cluster consumer perspective

Properties:

- no git-local assumptions
- no localhost fallback assumptions
- no developer-checkout requirements unless explicitly modeled in the runtime contract

### `developer-workflow`

Purpose:

- validate repo-aware local/developer behavior

Properties:

- may rely on git metadata
- may rely on local files or developer tooling
- should stop pretending to be runtime black-box validation

## Error Handling And Failure Semantics

The new structure must classify failures explicitly.

### Generation-time failure

If required topology, execution, runtime, or schema facts are contradictory or incomplete, generation fails immediately. Shared cross-consumer facts must not rely on silent defaults.

### Adapter validation failure

If a consumer misuses generated bindings, it should fail with a contract-specific error naming the violated contract object, not a generic runtime exception.

### Execution-context mismatch failure

If code intended for `platform-blackbox` attempts to rely on developer-only context, it should fail as an execution-context violation.

### Bootstrap prerequisite failure

If the environment is unavailable, that failure should appear in `bootstrap`, not cascade as dozens of downstream product failures.

## Migration Strategy

This is a hard-reset migration executed in strict phases.

### Phase 1: Establish contract domains and generators

- create `floe_core.contracts`
- add `topology`, `execution`, `schemas`, and `runtime` domains
- add generation targets for Python bindings, Helm-facing bindings, and shell/env outputs
- add contract tests for internal consistency

### Phase 2: Migrate highest-value runtime and schema contracts

Start with the highest-pain drift areas:

- runtime enums and shared constants such as OCI auth modes
- behavioral/result schemas such as CLI JSON outputs and machine-readable payloads

Rationale:

- improves failure signal quickly
- reduces ambiguity in integration failures

### Phase 3: Migrate topology and execution consumers

Move:

- chart job/test bindings
- test fixtures
- bootstrap scripts
- E2E runner env injection

Each consumer becomes an adapter over generated bindings.

### Phase 4: Delete legacy authoring paths and rebuild validation boundaries

- remove duplicate service/port/env tables
- remove stale aliases and compatibility paths
- move tests into `contract`, `bootstrap`, `platform-blackbox`, and `developer-workflow`
- remove tests whose assertions only exist to preserve duplicated literals

## Deletion Policy

The hard reset only works if legacy authoring paths are removed.

Delete immediately after migration of the affected domain:

- duplicate service maps in fixtures
- alternate env-binding logic in scripts
- stale enum names and compatibility aliases
- tests that rely on duplicated facts instead of generated contracts

Do not keep shadow compatibility layers unless required for the same branch migration.

## Success Criteria

The redesign is successful when all of the following are true:

- A shared fact such as a service name, port, auth mode, or output key is authored once.
- Charts, fixtures, scripts, and tests consume generated bindings or fail validation.
- Contract failures are distinguishable from bootstrap failures.
- Platform-blackbox failures reflect deployed behavior, not developer-local assumptions.
- Developer-workflow tests are explicitly scoped and no longer contaminate runtime validation.
- The number of hand-authored cross-consumer literals is materially reduced.

## Risks And Mitigations

### Risk: contract layer becomes a monolith

Mitigation:

- keep domains bounded
- avoid mixing unrelated facts
- enforce ownership by domain

### Risk: generators create opaque complexity

Mitigation:

- keep generated artifacts reviewable
- use thin adapters
- test generation outputs directly

### Risk: migration stalls halfway and leaves two systems alive

Mitigation:

- migrate one domain at a time
- delete legacy authoring paths immediately after each migration
- reject new duplicated facts during migration

### Risk: test split becomes naming-only and not behavioral

Mitigation:

- define hard execution rules per suite
- make context mismatch explicit failures
- stop allowing silent fallback behavior

## Acceptance Criteria

- `floe_core.contracts` exists with the four bounded domains defined in this spec.
- Shared runtime enums and machine-readable output schemas are sourced from that layer.
- Test-runner and bootstrap bindings are generated from the same contract system used by fixtures.
- The validation stack is split into contract, bootstrap, platform-blackbox, and developer-workflow categories.
- Legacy duplicate authoring paths for migrated domains are removed.

## Final Recommendation

Build a broad, generation-first contract layer now, and use a hard reset to move all cross-consumer operational facts into it. Start implementation with runtime/result schemas, then topology and execution bindings, then finish by deleting legacy authoring paths and restructuring the validation stack around the new boundaries.
