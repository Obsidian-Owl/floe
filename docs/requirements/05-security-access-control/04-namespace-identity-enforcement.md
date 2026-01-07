# REQ-436 to REQ-438: Namespace-Identity Security Enforcement

**Domain**: Security and Access Control
**Priority**: CRITICAL
**Status**: New specification (Architectural Validation 2026-01-07)

## Overview

This group of requirements enforces namespace-identity security at the RBAC and credential vending layer, preventing compromised job pods from accessing other products' namespaces. Integrates ADR-0030 (Namespace-Identity Model) with ADR-0022 (RBAC Model).

**Key Principle**: Namespace ownership verified at runtime, not just compile-time

**Security Threat Model**: Without runtime enforcement, a compromised job pod from `sales.customer_360` could:
1. Write to `marketing.campaigns` catalog namespace (cross-domain attack)
2. Register contracts under another product's identity (identity spoofing)
3. Corrupt namespace metadata (data integrity violation)

## Requirements

### REQ-436: Service Account Namespace Scoping **[New]**

**Requirement**: Service accounts MUST be scoped to product namespace via RBAC rules. A service account for `sales.customer_360` MUST NOT have permissions to write to `marketing.campaigns` namespace, even if both are in the same Kubernetes namespace.

**Rationale**: Prevents lateral movement in Data Mesh deployments where multiple products share infrastructure. Enforces product isolation at identity layer.

**Acceptance Criteria**:
- [ ] Service account annotations include product identity: `floe.dev/product-identity: sales.customer_360`
- [ ] RBAC rules restrict service account to product-specific catalog namespace
- [ ] Cross-product catalog write operations DENIED by CatalogPlugin
- [ ] Cross-product access requires explicit NetworkPolicy allowlist
- [ ] Service account tokens scoped to minimal permissions (catalog write for owned namespace only)
- [ ] RBAC audit logs capture cross-product access attempts

**Enforcement**:
- RBAC isolation tests (attempt cross-product write, expect denial)
- Service account scope validation tests
- Multi-product integration tests

**Constraints**:
- MUST validate product identity at CatalogPlugin layer (not just K8s RBAC)
- MUST deny cross-product access by default
- FORBIDDEN to share service accounts across products

**Configuration Example**:
```yaml
# Service account for sales.customer_360
apiVersion: v1
kind: ServiceAccount
metadata:
  name: floe-job-sales-customer-360
  namespace: floe-sales-domain  # Domain-specific K8s namespace
  annotations:
    floe.dev/product-identity: sales.customer_360
    floe.dev/repository: github.com/acme/sales-customer-360
    floe.dev/catalog-namespace: sales.customer_360  # Owned catalog namespace
---
# RBAC rule restricting to owned namespace
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: floe-job-sales-customer-360-role
  namespace: floe-sales-domain
rules:
  # Catalog API access (restricted to owned namespace)
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["polaris-catalog-config"]
    verbs: ["get"]

  # Secrets access (read-only, own credentials)
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["sales-customer-360-credentials"]
    verbs: ["get"]

  # NO cross-product permissions
```

**Test Coverage**:
- `tests/contract/test_namespace_identity_rbac.py`
- `tests/integration/test_cross_product_isolation.py`

**Traceability**:
- ADR-0030 (Namespace-Identity Model) - Product identity via catalog properties
- ADR-0022 (RBAC Model) - Service account isolation
- ADR-0038 (Data Mesh Architecture) - Multi-domain isolation
- Architectural validation finding: "Namespace-identity not enforced at RBAC layer"

---

### REQ-437: Catalog Write Validation **[New]**

**Requirement**: CatalogPlugin MUST validate that caller repository matches namespace owner before allowing catalog write operations. Prevents identity spoofing and cross-product namespace manipulation.

**Rationale**: K8s RBAC alone cannot prevent catalog namespace attacks if service accounts have broad permissions. Application-layer validation enforces ownership.

**Acceptance Criteria**:
- [ ] CatalogPlugin.create_namespace() validates caller identity before creation
- [ ] Namespace property `floe.product.repo` compared against service account annotation
- [ ] Repository ownership validation: `floe.dev/repository` annotation must match
- [ ] Validation algorithm executed before every write operation (create, update, delete)
- [ ] DENY operation if repository mismatch (with clear error message)
- [ ] Audit log entry created for all validation attempts (success and failure)

**Enforcement**:
- Catalog write validation tests
- Identity spoofing attack simulation tests
- Repository ownership verification tests

**Constraints**:
- MUST validate on EVERY write operation (no caching of permissions)
- MUST audit all validation attempts
- FORBIDDEN to bypass validation for "admin" users (enforce for all)

**Validation Algorithm**:
```python
# floe_catalog/plugin.py
from floe_core.errors import NamespaceOwnershipError

class PolarisPlugin(CatalogPlugin):
    def create_namespace(self, namespace: str, properties: dict) -> None:
        """Create catalog namespace with ownership validation."""

        # Step 1: Extract product identity from service account
        product_identity = self._get_service_account_annotation("floe.dev/product-identity")
        caller_repo = self._get_service_account_annotation("floe.dev/repository")

        # Step 2: Validate namespace matches product identity
        if namespace != product_identity:
            raise NamespaceOwnershipError(
                f"Product {product_identity} cannot create namespace {namespace}. "
                f"Namespace must match product identity."
            )

        # Step 3: Validate repository ownership
        namespace_repo = properties.get("floe.product.repo")
        if namespace_repo != caller_repo:
            # Audit security violation
            self._audit_security_event(
                event="namespace_ownership_violation",
                product=product_identity,
                namespace=namespace,
                caller_repo=caller_repo,
                expected_repo=namespace_repo
            )

            raise NamespaceOwnershipError(
                f"Repository mismatch: caller {caller_repo} cannot manage namespace "
                f"owned by {namespace_repo}"
            )

        # Step 4: Proceed with namespace creation
        self.catalog.create_namespace(namespace, properties)

        # Step 5: Audit successful operation
        self._audit_security_event(
            event="namespace_created",
            product=product_identity,
            namespace=namespace,
            repository=caller_repo
        )

    def _get_service_account_annotation(self, annotation: str) -> str:
        """Read annotation from mounted service account token."""
        # K8s mounts service account at /var/run/secrets/kubernetes.io/serviceaccount/
        # Use K8s API to read ServiceAccount annotations
        import kubernetes
        k8s_client = kubernetes.client.CoreV1Api()

        sa_name = os.getenv("KUBERNETES_SERVICE_ACCOUNT")
        namespace = os.getenv("KUBERNETES_NAMESPACE")

        sa = k8s_client.read_namespaced_service_account(sa_name, namespace)
        return sa.metadata.annotations.get(annotation)
```

**Error Messages**:
```python
# Namespace mismatch
NamespaceOwnershipError: Product sales.customer_360 cannot create namespace marketing.campaigns.
Namespace must match product identity.

# Repository mismatch
NamespaceOwnershipError: Repository mismatch: caller github.com/acme/sales-customer-360
cannot manage namespace owned by github.com/acme/marketing-campaigns
```

**Test Coverage**:
- `tests/unit/test_catalog_ownership_validation.py`
- `tests/integration/test_namespace_spoofing_prevention.py`

**Traceability**:
- ADR-0030 (Namespace-Identity Model) - Repository ownership validation
- platform-enforcement.md lines 590-896 (Catalog configuration)
- Architectural validation finding: "Catalog write operations lack ownership validation"

---

### REQ-438: Cross-Product Isolation **[New]**

**Requirement**: Network policies and RBAC MUST prevent cross-product access by default in Data Mesh deployments. Cross-domain data sharing requires explicit NetworkPolicy allowlist and documented data contracts.

**Rationale**: Default deny prevents accidental or malicious cross-product dependencies. Explicit allowlisting enables governance and lineage tracking.

**Acceptance Criteria**:
- [ ] Default NetworkPolicy denies cross-product traffic
- [ ] Cross-product access requires explicit NetworkPolicy: `floe.dev/allowed-products: "marketing.campaigns"`
- [ ] Cross-product data contracts REQUIRED for shared datasets
- [ ] OpenLineage events track cross-product data flows
- [ ] RBAC denies cross-product catalog access by default
- [ ] Audit logs capture cross-product access attempts

**Enforcement**:
- Network policy isolation tests
- Cross-product access denial tests
- Data contract enforcement tests

**Constraints**:
- MUST deny cross-product access by default
- MUST require data contract for cross-product data sharing
- FORBIDDEN to bypass isolation without explicit allowlist

**Default NetworkPolicy**:
```yaml
# Default deny cross-product traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-cross-product
  namespace: floe-sales-domain
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress: []  # Deny all ingress by default
  egress:
    # Allow DNS
    - to:
      - namespaceSelector:
          matchLabels:
            name: kube-system
      ports:
        - protocol: UDP
          port: 53

    # Allow platform services (Polaris, OTLP Collector)
    - to:
      - namespaceSelector:
          matchLabels:
            floe.dev/namespace-type: platform

    # Deny other domains (no cross-product access)
```

**Cross-Product Allowlist**:
```yaml
# Explicit cross-product access for data sharing
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-marketing-campaigns-access
  namespace: floe-sales-domain
  annotations:
    floe.dev/data-contract: sales.customer_360/shared_to_marketing_v1
    floe.dev/justification: "Marketing needs customer segments for campaign targeting"
spec:
  podSelector:
    matchLabels:
      floe.dev/product: sales.customer_360
  policyTypes:
    - Egress
  egress:
    # Allow access to marketing.campaigns Polaris namespace
    - to:
      - namespaceSelector:
          matchLabels:
            floe.dev/domain: marketing
      ports:
        - protocol: TCP
          port: 8181  # Polaris catalog API
```

**Data Contract Requirement**:
```yaml
# Data contract for cross-product sharing
# sales.customer_360/contracts/shared_to_marketing_v1.yaml
dataContractSpecification: 0.9.3
id: sales.customer_360/shared_to_marketing_v1
info:
  title: Customer Segments Shared to Marketing
  version: 1.0.0
  owner: Sales Platform Team

consumers:
  - name: marketing.campaigns
    justification: Campaign targeting
    access_pattern: read-only
    sla: 24h freshness

schema:
  type: iceberg
  fields:
    - name: customer_id
      type: string
      classification: pii
      required: true
    - name: segment
      type: string
      required: true
```

**Test Coverage**:
- `tests/contract/test_cross_product_isolation.py`
- `tests/integration/test_data_mesh_networking.py`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) - Domain isolation
- ADR-0022 (RBAC Model) - Network policies
- ADR-0026 (Data Contract Architecture) - Cross-product contracts
- Architectural validation finding: "Cross-product isolation not enforced"

---

## Data Mesh Deployment Example

**Scenario**: Sales domain and Marketing domain in separate Kubernetes namespaces

```yaml
# Namespace: floe-sales-domain
# Products: sales.customer_360, sales.order_history

# Namespace: floe-marketing-domain
# Products: marketing.campaigns, marketing.email_lists

# Default: No cross-domain access
# Explicit allowlist: sales.customer_360 → marketing.campaigns (via data contract)
```

**Security Model**:
1. **Namespace isolation**: K8s namespace per domain (`floe-sales-domain`, `floe-marketing-domain`)
2. **Product identity**: Service account annotations (`floe.dev/product-identity`)
3. **Catalog ownership**: Validated at CatalogPlugin layer (REQ-437)
4. **Network isolation**: NetworkPolicy default deny (REQ-438)
5. **Data contracts**: Required for cross-product sharing (ADR-0026)

## Related Requirements

- **REQ-400 to REQ-415**: RBAC Model (service account isolation)
- **REQ-416 to REQ-425**: Network Policies (traffic segmentation)
- **REQ-431 to REQ-435**: Credential Vending (namespace-scoped credentials)
- **REQ-221 to REQ-240**: Data Contracts (cross-product sharing governance)

## References

- ADR-0030: Namespace-Identity Model
- ADR-0022: Security RBAC Model
- ADR-0038: Data Mesh Architecture
- Architectural Validation Report (2026-01-07)
