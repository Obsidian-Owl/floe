# Epic 7A: Identity & Secrets

## Summary

Identity and secrets management provides secure credential handling across the floe platform. This includes integration with external identity providers (OAuth2, OIDC), secret stores (Vault, K8s Secrets), and secure credential resolution at runtime.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-07a-identity-secrets](https://linear.app/obsidianowl/project/floe-07a-identity-secrets-f4ffc9929758)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-400 | IdentityPlugin ABC | CRITICAL |
| REQ-401 | SecretsPlugin ABC | CRITICAL |
| REQ-402 | OAuth2/OIDC integration | HIGH |
| REQ-403 | Service account management | HIGH |
| REQ-404 | Token refresh handling | HIGH |
| REQ-405 | Kubernetes Secrets integration | CRITICAL |
| REQ-406 | HashiCorp Vault integration | HIGH |
| REQ-407 | AWS Secrets Manager interface | MEDIUM |
| REQ-408 | Secret rotation support | HIGH |
| REQ-409 | Credential caching | MEDIUM |
| REQ-410 | Audit logging for secret access | HIGH |
| REQ-411 | SecretReference resolution | CRITICAL |
| REQ-412 | Environment variable injection | HIGH |
| REQ-413 | Secret encryption at rest | HIGH |
| REQ-414 | Principal management | HIGH |
| REQ-415 | Role mapping | HIGH |
| REQ-416 | Token validation | HIGH |
| REQ-417 | Session management | MEDIUM |
| REQ-418 | Multi-tenant isolation | HIGH |
| REQ-419 | Credential expiration handling | HIGH |
| REQ-420 | Secret versioning | MEDIUM |
| REQ-421 | Emergency access procedures | MEDIUM |
| REQ-422 | Compliance reporting | MEDIUM |
| REQ-423 | Secret scanning prevention | HIGH |
| REQ-424 | Identity federation | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0040](../../../architecture/adr/0040-identity-architecture.md) - Identity architecture
- [ADR-0013](../../../architecture/adr/0013-credential-resolution.md) - Runtime credential resolution

### Contracts
- `IdentityPlugin` - Identity provider ABC
- `SecretsPlugin` - Secret store ABC
- `SecretReference` - Secret placeholder model

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── plugin_interfaces.py         # IdentityPlugin, SecretsPlugin ABCs
├── security/
│   ├── __init__.py
│   ├── identity.py              # Identity utilities
│   ├── secrets.py               # Secret resolution
│   └── references.py            # SecretReference model
└── schemas/
    └── secret_reference.py      # SecretReference schema

plugins/floe-secrets-k8s/
├── src/floe_secrets_k8s/
│   ├── __init__.py
│   ├── plugin.py                # K8sSecretsPlugin
│   └── config.py
└── tests/
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 2A | SecretReference in manifest |
| Blocks | Epic 4C | Catalog uses identity for access control |
| Blocks | Epic 7B | RBAC uses identity |
| Blocks | Epic 9A | K8s deployment configures secrets |

---

## User Stories (for SpecKit)

### US1: SecretReference Resolution (P0)
**As a** data engineer
**I want** secrets resolved at runtime
**So that** credentials never appear in configuration files

**Acceptance Criteria**:
- [ ] `${secret:vault/path/to/secret}` syntax
- [ ] Resolution happens at runtime, not compile time
- [ ] Multiple secret backends supported
- [ ] Fallback to environment variables

### US2: Kubernetes Secrets Integration (P0)
**As a** platform operator
**I want** K8s Secrets as a secret backend
**So that** I can use native Kubernetes security

**Acceptance Criteria**:
- [ ] `K8sSecretsPlugin` implements ABC
- [ ] Secret lookup by name
- [ ] Namespace-scoped secrets
- [ ] Secret refresh on change

### US3: OAuth2/OIDC Integration (P1)
**As a** platform operator
**I want** external identity providers
**So that** I can use corporate SSO

**Acceptance Criteria**:
- [ ] OIDC discovery support
- [ ] Token validation
- [ ] Role claim mapping
- [ ] Token refresh handling

### US4: Vault Integration (P1)
**As a** platform operator
**I want** HashiCorp Vault integration
**So that** I can use enterprise secret management

**Acceptance Criteria**:
- [ ] Vault KV v2 support
- [ ] AppRole authentication
- [ ] Kubernetes auth method
- [ ] Secret lease renewal

### US5: Audit Logging (P2)
**As a** security officer
**I want** secret access audited
**So that** I can track credential usage

**Acceptance Criteria**:
- [ ] All secret access logged
- [ ] Requester identity captured
- [ ] Timestamp and context recorded
- [ ] Integration with SIEM

---

## Technical Notes

### Key Decisions
- Secrets are NEVER stored in floe configuration
- SecretReference is a placeholder resolved at runtime
- K8s Secrets is the default backend (zero-config for K8s deployments)
- Vault integration is optional but recommended for enterprise

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Secret exposure in logs | MEDIUM | CRITICAL | SecretStr, log scrubbing |
| Token expiration | MEDIUM | HIGH | Automatic refresh, retry |
| Vault availability | MEDIUM | HIGH | Fallback secrets, caching |

### Test Strategy
- **Unit**: `plugins/floe-secrets-k8s/tests/unit/test_plugin.py`
- **Integration**: `plugins/floe-secrets-k8s/tests/integration/test_k8s_secrets.py`
- **Contract**: `tests/contract/test_secrets_plugin_abc.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/05-security-access-control/`
- `docs/architecture/security/`
- `packages/floe-core/src/floe_core/security/`
- `plugins/floe-secrets-k8s/`

### Related Existing Code
- SecretReference schema from Epic 2A

### External Dependencies
- `kubernetes>=26.0.0`
- `hvac>=1.2.0` (Vault client)
- `authlib>=1.2.0` (OAuth2/OIDC)
