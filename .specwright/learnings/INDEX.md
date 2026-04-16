# Learnings Index

Compacted themes from work unit learnings. Last updated: 2026-02-17 (WU-12 added).

---

## Theme 1: Test Quality Discipline

**Work Units**: WU-6, WU-8, WU-9, WU-12

Test quality improvements surfaced across every work unit. Key patterns promoted:

| Rule | Source | Destination |
|------|--------|-------------|
| Exact exception types in `pytest.raises()` | WU-6 | Constitution V |
| `strict=True` on all `xfail` markers | WU-8 | Constitution V |
| Negative-path enforcement tests required | WU-8 | Constitution V |
| Deterministic count assertions (`== N`, never `>= N`) | WU-12 | Constitution V |
| Autouse fixture scoping to narrowest level | WU-6 | Patterns P1 |
| Health check strict status validation | WU-8 | Patterns P5 |
| Test migration must preserve coverage | WU-8 | Patterns P6 |
| CI security review complements gate-security | WU-9 | Patterns P11 |

**Insight**: gate-tests (adversarial auditor) is the highest-yield gate. It found actionable issues in every WU that included test changes. Assertion strength is the #1 most-recurring finding (WU-6, WU-8, WU-11, WU-12).

---

## Theme 2: Security-First at All Layers

**Work Units**: WU-6, WU-9, WU-12

Security patterns evolved from basic input validation to attack surface analysis to container hardening:

| Rule | Source | Destination |
|------|--------|-------------|
| Internal boundary validation (non-empty, max-length) | WU-6 | Constitution VI |
| Endpoint SSRF prevention (scheme + private network) | WU-9 | Constitution VI |
| Non-root USER placement in Dockerfiles | WU-12 | Patterns P20 |

**Insight**: Gate-security catches code patterns; CI security review catches attack surface. Both are needed. WU-12 extended this to container security (non-root runtime).

---

## Theme 3: Schema Change Ripple Effects

**Work Units**: WU-6, WU-8, WU-9

The recurring pattern: a core schema/config change creates predictable downstream work that isn't planned.

| Ripple | WU | Pattern |
|--------|-----|---------|
| New types need `__init__.py` re-exports | WU-6 | P4 |
| Port migration needs dual-target testing | WU-8 | P6 |
| Version bump needs golden fixture cascade | WU-9 | P9 |
| Fixture changes need secrets baseline update | WU-9 | P10 |
| All of the above: Schema Change Ripple Checklist | WU-9 | P12 |

**Insight**: WU-9 had a 1:1 task-to-fixup commit ratio. Building downstream steps into the plan eliminates post-verify churn.

---

## Theme 4: Verification System Effectiveness

**Work Units**: WU-6, WU-8

The 5-gate system found actionable findings in 7 of 8 WUs (WU-1 through WU-8). Total across the epic: 8 BLOCKs, 61 WARNs.

| Pattern | Source | Destination |
|---------|--------|-------------|
| Structured cleanup plan for >5 WARNs | WU-6 | P3 |
| Never skip verification, even for simple changes | WU-8 | P8 |
| Single-PID multi-port kubectl port-forward | WU-8 | P7 |

**Insight**: gate-tests catches the most issues. gate-wiring catches layer violations early. gate-spec ensures ACs are met.

---

## Theme 5: Docker Packaging Discipline

**Work Units**: WU-11, WU-12

Docker image builds evolved across two WUs: WU-11 established structural testing, WU-12 replaced vendor images entirely with uv-based builds.

| Rule | Source | Destination |
|------|--------|-------------|
| Explicit dbt --profiles-dir | WU-11 | Patterns P13 |
| --no-deps requires dependency compatibility matrix | WU-11 | Patterns P14 |
| Base image version must match package constraints | WU-11 | Patterns P15 |
| Selective COPY — only copy what's installed | WU-11 | Patterns P16 |
| uv export as vendor image replacement | WU-12 | Patterns P18 |
| Python stdlib version guards (sys.version_info) | WU-12 | Patterns P19 |
| Non-root USER placement after file operations | WU-12 | Patterns P20 |
| Docker extras for runtime-only dependencies | WU-12 | Patterns P21 |

**Insight**: WU-11 discovered that vendor base images create version conflicts (P14/P15). WU-12 eliminated them entirely with `uv export --frozen --require-hashes`. Together they form a complete Docker packaging discipline: structural tests as first tier, uv-based builds as architecture, selective COPY, non-root runtime, extras for env separation.

---

## Theme 6: Makefile Build Hygiene

**Work Units**: WU-11

Make targets should form a clean DAG without duplicated work. Redundant compilation creates drift risk when the two paths use different flags.

| Rule | Source | Destination |
|------|--------|-------------|
| No redundant compilation in target bodies | WU-11 | Patterns P17 |

**Insight**: PR reviewers catch "works but wasteful" issues that automated gates miss. Human/bot code review remains a valuable complementary layer.

---

## Theme 7: Structural Testing as First Tier

**Work Units**: WU-8, WU-11, WU-12

File-parsing tests that validate structure on disk (Dockerfile instructions, Makefile targets, Helm values, generated code) provide high coverage at near-zero cost. They complement runtime tests, not replace them.

| Rule | Source | Destination |
|------|--------|-------------|
| Structural parse-and-assert tests for packaging pipelines | WU-11 | Constitution V |
| Deterministic count assertions in structural tests | WU-12 | Constitution V |

**Insight**: WU-11 achieved 96 tests, WU-12 expanded to 118 tests validating 6+ artifact types in < 0.25 seconds. The only gap remains runtime behavior, which requires K8s.
