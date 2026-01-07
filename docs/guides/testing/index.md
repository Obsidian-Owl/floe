# Testing Guide

This section covers quality requirements, testing strategy, and CI/CD for floe.

> **Note**: This guide was split from [08-quality.md](../08-quality.md) for LLM context efficiency.
> The original ARC42 file redirects here.

---

## Quality Goals

| Quality | Target | Measurement |
|---------|--------|-------------|
| **Reliability** | Zero data loss | Integration tests, property tests |
| **Portability** | Works on macOS, Linux, Windows | CI matrix |
| **Performance** | CLI startup < 500ms | Benchmark suite |
| **Maintainability** | < 30 min to fix typical bug | Code review metrics |
| **Testability** | > 80% code coverage | Coverage reports |
| **Usability** | < 5 min to first run | User testing |

---

## Testing Strategy Overview

### Test Pyramid

```
                    ┌─────────┐
                    │   E2E   │  ← Few, slow, high confidence
                    │  Tests  │
                    ├─────────┤
                    │ Integr- │
                    │  ation  │  ← Some, medium speed
                    │  Tests  │
                    ├─────────┤
                    │         │
                    │  Unit   │  ← Many, fast, isolated
                    │  Tests  │
                    │         │
                    └─────────┘
```

### Test Types

| Type | Scope | Execution Environment | Speed |
|------|-------|----------------------|-------|
| **Unit** | Single function/class | CI runner (local) | < 1s |
| **Integration** | Component interactions | **K8s pods (Kind cluster)** | < 2min |
| **E2E** | Full workflows | **K8s pods (Full Helm deploy)** | < 10min |
| **Performance** | Benchmarks | K8s pods (production-like) | varies |

### Infrastructure Parity Principle

> **"Test like you fly, fly like you test"** — Integration and E2E tests MUST run in Kubernetes pods, not on CI runners with Docker Compose.

**Rationale:**
- Production runs in K8s → Tests must run in K8s
- Networking, service discovery, resource limits differ between Docker Compose and K8s
- Helm chart bugs only surface when deployed to K8s
- Pod lifecycle, health checks, and restart policies need real testing

---

## Guide Contents

| Guide | Description |
|-------|-------------|
| [Unit Testing](unit-testing.md) | Unit test patterns, structure, property-based testing |
| [Integration Testing](integration-testing.md) | K8s-native integration tests, fixtures |
| [E2E Testing](e2e-testing.md) | End-to-end workflow testing |
| [K8s Testing Infrastructure](k8s-infrastructure.md) | Kind clusters, test pod architecture |
| [CI/CD Pipeline](ci-cd.md) | GitHub Actions workflows, release process |
| [Code Quality](code-quality.md) | Style guides, linting, pre-commit configuration |

---

## Quick Reference

### Commands

```bash
# Run unit tests (fast, no K8s)
uv run pytest tests/unit

# Run integration tests (requires Kind cluster)
kubectl apply -f tests/integration/test-job.yaml

# Run E2E tests (requires full stack)
kubectl apply -f tests/e2e/test-job.yaml

# Local Kind cluster setup
kind create cluster --name floe-dev
helm install floe-dev ./charts/floe-platform --set minimal=true
```

### Related Documentation

- [ADR-0017: K8s Testing Infrastructure](../../architecture/adr/0017-k8s-testing-infrastructure.md)
- [TESTING.md](/TESTING.md) - Root-level testing reference
- [Testing Standards](/.claude/rules/testing-standards.md) - Development standards
