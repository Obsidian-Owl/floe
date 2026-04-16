# Decisions: Test Infrastructure Convergence

## D-1: Build on existing infrastructure rather than rebuild

**Context**: In-cluster test runner (Dockerfile, Jobs, RBAC, runner scripts) already
exists and is functional. Question: extend it or start fresh?

**Decision**: Extend. The existing infrastructure is well-built, handles image loading,
Job lifecycle, log streaming, and artifact extraction. Gaps are narrow (DevPod support,
observability, security propagation).

**Rule applied**: DISAMBIGUATION — simplest path that satisfies requirements. Rebuild
would be wasteful given 90% completion.

## D-2: Abandon current work `e2e-permanent-fixes` to start new design

**Context**: `e2e-permanent-fixes` was at unit 9/9 (`e2e-proof`) in building state.
This new design supersedes the proof-of-concept approach with a structural solution.

**Decision**: Abandon. The permanent fixes (units 1-8) are shipped and merged. The
proof unit was about validating those fixes, which is subsumed by this convergence work.

**Rule applied**: State protocol — transition from `building` to `abandoned`, then
create new work.

## D-3: Three-tier observability (structured output + OTel traces + failure log extraction)

**Context**: User explicitly requested "log extraction / observability baked in."
Options ranged from simple log capture to full service mesh.

**Decision**: Three practical layers: (A) pytest plugins for structured reports,
(B) OTel SDK traces from test code to in-cluster collector, (C) pod log extraction
on failure. No service mesh or sidecar injection.

**Rule applied**: DISAMBIGUATION — maximum debugging value with minimum infrastructure.
Service mesh rejected per charter's "minimize operational complexity" principle.

## D-4: PSS exemption for Marquez rather than custom image

**Context**: Marquez runs as root, no upstream fix. Options: custom Dockerfile,
PSS exemption, or accept and document.

**Decision**: PSS namespace exemption with documentation. Custom image risks breaking
Marquez internals and creates maintenance burden for upstream updates.

**Rule applied**: Reversibility — exemption is easily removed when upstream fixes the
issue. Custom image creates ongoing fork maintenance.

## D-6: Marquez PSS — accept and document, defer namespace separation

**Context**: Architect review identified that PSS admission is namespace-scoped only.
Pod-level exemption labels don't exist in standard K8s PSA. Original design suggested
pod-level label selector — this is impossible without Kyverno/OPA.

**Decision**: Accept Marquez running as root for now. Document in AUDIT.md. Defer
namespace separation to a follow-up work unit (adds cross-namespace DNS complexity).

**Rule applied**: Architect review BLOCK resolution — design updated to remove
the impossible pod-level exemption claim.

## D-7: DevPod image loading — docker save pipe, not registry

**Context**: Architect review noted registry push URL discovery is under-specified.
Registry requires NodePort tunnel from host to DevPod cluster.

**Decision**: Use `docker save | ssh devpod | docker load` as primary DevPod path.
This only needs SSH (guaranteed by DevPod). Registry push deferred as optimization.

**Rule applied**: Architect review WARN resolution — simplest reliable path first.

## D-8: Subchart security context key paths — verified and enumerated

**Context**: Architect BLOCK — YAML anchors work syntactically but target keys must
match subchart schemas. Original design showed incorrect key paths.

**Decision**: Verified all subchart schemas via `helm show values`. Correct key paths
documented in design.md. Each subchart uses a different schema (Dagster per-component,
Bitnami `enabled` flag for MinIO, top-level for OTel). Design updated with accurate
mappings.

**Rule applied**: Architect review BLOCK resolution — verified against source of truth.

## D-5: Registry-based image loading for DevPod with pipe fallback

**Context**: `kind load docker-image` doesn't work from host to remote Kind cluster.
Options: in-cluster registry, `docker save | ssh | docker load`, or build image
on remote.

**Decision**: Primary: push to in-cluster registry (already provisioned). Fallback:
`docker save | ssh | docker load` pipe. Auto-detect in runner script.

**Rule applied**: DISAMBIGUATION — registry is the standard pattern, pipe is the
reliable fallback. Both use infrastructure that already exists.

## D-9: Three work units (planning phase)

**Context**: Design has 5 work streams. Needed to decompose into independently
buildable, testable units.

**Decision**: Three units:
1. **in-cluster-runner** (streams 1 & 4): Runner + DevPod + orchestrator. Foundation.
2. **test-observability** (stream 2): Dockerfile + Job manifest + log extraction. Depends on 1.
3. **security-hardening** (streams 3 & 5): Helm values + contract test + containerized tools. Independent.

**Rationale**: Streams 1 & 4 share the same files (`test-e2e-cluster.sh`, Makefile)
and are tightly coupled. Streams 3 & 5 share the Helm/Makefile domain but touch
different files than streams 1 & 2. Stream 2 depends on the runner structure from 1.

**Rule applied**: DISAMBIGUATION — grouping by file coupling and dependency order.
Unit 3 can be built in parallel with units 1+2 if agent teams are available.
