# OpenChoreo and Floe Hypotheses

Date: 2026-04-30

## Status Legend

- Pending: evidence has not been collected.
- Pass: evidence supports the hypothesis.
- Partial: evidence supports part of the hypothesis but leaves important risk.
- Fail: evidence contradicts the hypothesis.

## Matrix

| ID | Hypothesis | Evidence Required | Status | Evidence Summary | Confidence |
| --- | --- | --- | --- | --- | --- |
| H1 | OpenChoreo can improve Floe's developer experience by exposing higher-level project, component, environment, workflow, and observability abstractions around Floe data products. | A clear mapping from `floe.yaml` to OpenChoreo project/component UX with less user-facing Kubernetes detail. | Pending | Collected in Task 2 or Task 3 | Low |
| H2 | OpenChoreo can simplify Floe's physical architecture by taking ownership of some Kubernetes lifecycle concerns currently handled through Helm, GitOps examples, RBAC generation, network policy generation, and deployment glue. | Identified Floe-owned responsibilities that OpenChoreo can own without weakening Floe governance. | Pending | Collected in Task 2 or Task 3 | Low |
| H3 | Floe should keep ownership of data-specific semantics: configuration, plugin selection, compiled artifact contracts, dbt, Iceberg, lineage, quality gates, and governance enforcement. | Floe contracts remain source of truth and OpenChoreo consumes generated outputs. | Pending | Collected in Task 2 or Task 3 | Low |
| H4 | OpenChoreo is not a direct replacement for Floe's `OrchestratorPlugin`; it is closer to a platform/developer-experience control plane. | The best integration point lands outside the existing Dagster/Airflow/Prefect orchestrator abstraction. | Pending | Collected in Task 2 or Task 3 | Low |
| H5 | Adoption is only valuable if a Floe data product can be represented in OpenChoreo without breaking downward-only configuration flow or exposing low-level OpenChoreo CRDs to data engineers. | A proof resource set can be generated from existing Floe inputs and environment/promotion data stays outside `floe.yaml`. | Pending | Collected in Task 2 or Task 3 | Low |

## Decision Rule

Recommend the proof spike only if H3 and H4 are Pass or Partial, and at least one of H1 or H2 is Pass or Partial. Recommend watch or reject if H3 or H4 fails.
