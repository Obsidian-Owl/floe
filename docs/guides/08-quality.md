# 08. Quality

> **This document has been split for LLM context efficiency.**
>
> The full testing and quality documentation is now located in the [testing/](testing/) directory.

---

## Quick Navigation

| Guide | Description |
|-------|-------------|
| [Testing Index](testing/index.md) | Overview, quality goals, testing strategy |
| [Unit Testing](testing/unit-testing.md) | Unit test patterns, property-based testing |
| [Integration Testing](testing/integration-testing.md) | K8s-native integration tests |
| [E2E Testing](testing/e2e-testing.md) | End-to-end workflow testing |
| [K8s Infrastructure](testing/k8s-infrastructure.md) | Kind clusters, test pod architecture |
| [CI/CD Pipeline](testing/ci-cd.md) | GitHub Actions workflows |
| [Code Quality](testing/code-quality.md) | Style guides, linting, pre-commit |

---

## Quality Goals (Summary)

| Quality | Target | Measurement |
|---------|--------|-------------|
| **Reliability** | Zero data loss | Integration tests, property tests |
| **Portability** | Works on macOS, Linux, Windows | CI matrix |
| **Performance** | CLI startup < 500ms | Benchmark suite |
| **Maintainability** | < 30 min to fix typical bug | Code review metrics |
| **Testability** | > 80% code coverage | Coverage reports |
| **Usability** | < 5 min to first run | User testing |

---

## Related Documentation

- [ADR-0017: K8s Testing Infrastructure](../architecture/adr/0017-k8s-testing-infrastructure.md)
- [TESTING.md](/TESTING.md) - Root-level testing reference
