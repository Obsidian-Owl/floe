# Feature Specification: Catalog Plugin

**Feature Branch**: `001-catalog-plugin`
**Created**: 2026-01-09
**Status**: Draft
**Input**: User description: "Implement CatalogPlugin ABC and Polaris reference implementation for metadata catalog management"

## Clarifications

### Session 2026-01-09

- Q: How should CatalogPlugin ABC handle credential vending for catalogs that don't support it? → A: ABC requires `vend_credentials()` method; unsupported catalogs (e.g., Hive Metastore) raise `NotSupportedError`
- Q: Should spec use architecture's `create_catalog()`/`load_catalog()` or existing code's `connect()` pattern? → A: Use `connect()` pattern; catalog creation is a one-time admin operation outside plugin scope
- Q: Should catalog operations emit OpenTelemetry traces in addition to structured logs? → A: Required; all catalog operations emit OTel spans with duration, status, and context per REQ-038

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plugin Developer Implements Custom Catalog Adapter (Priority: P0)

A plugin developer needs to create a catalog adapter for their organization's metadata catalog system. They require a well-defined interface (Abstract Base Class) that specifies exactly what operations a catalog must support, enabling them to implement adapters for catalogs like AWS Glue, Hive Metastore, or proprietary systems.

**Why this priority**: Without a clear ABC definition, no catalog integrations can be built. This is the foundation that all catalog plugins depend on.

**Independent Test**: Can be fully tested by implementing a mock catalog that satisfies all ABC requirements, verifying the interface is complete and usable without any external dependencies.

**Acceptance Scenarios**:

1. **Given** a developer creating a new catalog adapter, **When** they inherit from CatalogPlugin ABC, **Then** they receive clear errors for any unimplemented required methods
2. **Given** a complete catalog plugin implementation, **When** registered with the plugin registry, **Then** it is discoverable and instantiable by the platform
3. **Given** the CatalogPlugin ABC, **When** a developer reviews the interface, **Then** all method signatures include typed parameters and return values with documentation

---

### User Story 2 - Platform Operator Uses Polaris as Default Catalog (Priority: P0)

A platform operator deploys floe with Apache Polaris as the default metadata catalog. They need Polaris integration that provides Iceberg REST catalog capabilities with proper authentication, allowing data teams to register and query table metadata.

**Why this priority**: Polaris is the reference implementation and default catalog. Platform operators need a working catalog from day one to manage table metadata.

**Independent Test**: Can be fully tested by configuring Polaris connection, authenticating, and performing basic catalog operations (create namespace, register table, list tables).

**Acceptance Scenarios**:

1. **Given** valid Polaris connection configuration, **When** the plugin initializes, **Then** it establishes authenticated connection to Polaris server
2. **Given** an authenticated Polaris connection, **When** a table is registered, **Then** the table metadata appears in the Polaris catalog
3. **Given** Polaris server is temporarily unavailable, **When** the plugin attempts connection, **Then** it provides clear error messages and retries with configurable backoff
4. **Given** OAuth2 credentials, **When** the plugin authenticates, **Then** tokens are securely managed and refreshed before expiration

---

### User Story 3 - Platform Operator Manages Namespaces (Priority: P1)

A platform operator needs to organize tables into logical namespaces that reflect their data architecture (e.g., domain.product.layer hierarchy). They want namespaces created automatically based on configuration, with proper metadata like owner and storage location.

**Why this priority**: Namespace organization is essential for multi-tenant and multi-domain data platforms. Without namespaces, all tables exist in a flat structure that becomes unmanageable.

**Independent Test**: Can be fully tested by creating hierarchical namespaces, setting properties, and verifying the namespace structure matches the configured hierarchy.

**Acceptance Scenarios**:

1. **Given** a namespace configuration in floe.yaml, **When** the platform initializes, **Then** the corresponding namespace hierarchy is created in the catalog
2. **Given** a namespace with properties (owner, location), **When** created, **Then** the properties are retrievable from the catalog
3. **Given** an existing namespace, **When** a data product is removed, **Then** the namespace can be cleaned up if empty
4. **Given** a hierarchical namespace path (e.g., "sales.customers.bronze"), **When** the intermediate namespaces don't exist, **Then** they are created automatically

---

### User Story 4 - Platform Operator Registers and Lists Tables (Priority: P1)

A platform operator needs to register Iceberg tables in the catalog and query the catalog to discover available tables. This enables data discovery and allows downstream consumers to find and access data assets.

**Why this priority**: Table registration is the core purpose of a catalog. Without it, the catalog provides no value for data discovery.

**Independent Test**: Can be fully tested by registering a table with metadata, listing tables in namespace, and verifying table metadata is accurate.

**Acceptance Scenarios**:

1. **Given** a valid table definition, **When** registered in a namespace, **Then** the table appears in table listings for that namespace
2. **Given** a registered table, **When** queried for metadata, **Then** schema, location, and properties are returned accurately
3. **Given** multiple tables across namespaces, **When** listing tables with filters, **Then** only matching tables are returned
4. **Given** a table that already exists, **When** registration is attempted, **Then** the system handles the conflict appropriately (error or update based on configuration)

---

### User Story 5 - Security Engineer Configures Access Control (Priority: P1)

A security engineer needs to control who can access which tables and namespaces. They want to manage principals (users/roles), assign permissions, and integrate with existing identity systems to ensure data governance compliance.

**Why this priority**: Access control is critical for production deployments with sensitive data. Without it, all data is accessible to everyone with catalog access.

**Independent Test**: Can be fully tested by creating principals, assigning roles to namespaces/tables, and verifying permission checks work correctly.

**Acceptance Scenarios**:

1. **Given** a catalog that supports access control, **When** a principal is created, **Then** the principal can be assigned roles
2. **Given** a role with namespace-level permissions, **When** assigned to a principal, **Then** that principal can only access permitted namespaces
3. **Given** table-level privileges, **When** granted to a role, **Then** the role has appropriate read/write access
4. **Given** a catalog without access control support, **When** access control operations are attempted, **Then** the system clearly indicates the feature is unsupported

---

### User Story 6 - Platform Operator Monitors Catalog Health (Priority: P2)

A platform operator needs to monitor the health and availability of the catalog to ensure reliable data platform operations. They want health checks that can be integrated with existing monitoring systems.

**Why this priority**: Health monitoring enables proactive issue detection but is not required for basic catalog functionality.

**Independent Test**: Can be fully tested by calling health check endpoints and verifying appropriate status reporting.

**Acceptance Scenarios**:

1. **Given** a running catalog plugin, **When** health is checked, **Then** connection status and response time are reported
2. **Given** a degraded catalog connection, **When** health is checked, **Then** the degraded state is reported with diagnostic details
3. **Given** health check integration enabled, **When** the catalog becomes unavailable, **Then** alerts can be triggered through standard observability channels

---

### Edge Cases

- What happens when the catalog server is unreachable during startup?
- How does the system handle authentication token expiration mid-operation?
- What happens when namespace creation fails due to naming conflicts?
- How does the system handle concurrent table registrations for the same table?
- What happens when a parent namespace is deleted while child namespaces exist?
- How does the system behave when catalog schema versions are incompatible?

## Requirements *(mandatory)*

### Functional Requirements

**CatalogPlugin ABC (Core Interface)**

- **FR-001**: System MUST define a CatalogPlugin abstract base class with `connect()` method that returns a PyIceberg-compatible Catalog instance
- **FR-002**: System MUST define namespace management methods in CatalogPlugin (create_namespace, list_namespaces, delete_namespace)
- **FR-003**: System MUST define table operation methods in CatalogPlugin (create_table, list_tables, drop_table, update_table_metadata)
- **FR-004**: System MUST require all CatalogPlugin implementations to provide plugin metadata (name, version, floe_api_version)
- **FR-005**: System MUST allow CatalogPlugin implementations to declare optional capabilities (access control, schema versioning)

**Polaris Reference Implementation**

- **FR-006**: System MUST provide a PolarisCatalogPlugin that implements the CatalogPlugin ABC
- **FR-007**: System MUST support OAuth2 authentication for Polaris connections
- **FR-008**: System MUST support configurable connection parameters (endpoint, credentials, timeout, retry policy)
- **FR-009**: System MUST handle Polaris REST API interactions for all catalog operations

**Namespace Management**

- **FR-010**: System MUST support creating namespaces with configurable properties (location, owner, custom metadata)
- **FR-011**: System MUST support hierarchical namespace paths using dot notation (e.g., "domain.product.layer")
- **FR-012**: System MUST support listing namespaces with optional filtering
- **FR-013**: System MUST support deleting empty namespaces

**Table Operations**

- **FR-014**: System MUST support creating Iceberg tables with schema, location, and properties
- **FR-015**: System MUST support listing tables within a namespace
- **FR-016**: System MUST support retrieving table metadata including schema and statistics
- **FR-017**: System MUST support updating table properties
- **FR-018**: System MUST support dropping tables with metadata cleanup

**Credential Vending (Core ABC Method)**

- **FR-019**: System MUST define `vend_credentials()` as a required abstract method in CatalogPlugin ABC
- **FR-020**: System MUST return short-lived, scoped credentials for table access operations (READ, WRITE)
- **FR-021**: Vended credentials MUST include expiration timestamp and be valid for no more than 24 hours
- **FR-022**: Catalogs that do not support credential vending MUST raise `NotSupportedError` with actionable message
- **FR-023**: System MUST support the Iceberg REST `X-Iceberg-Access-Delegation: vended-credentials` header pattern

**Access Control (Optional Capability)**

- **FR-024**: System MUST support creating and managing principals (users, service accounts)
- **FR-025**: System MUST support creating and managing roles with privilege sets
- **FR-026**: System MUST support granting privileges at namespace and table levels
- **FR-027**: System MUST clearly indicate when a catalog does not support access control

**Health and Observability**

- **FR-028**: System MUST provide a health check method that reports catalog availability
- **FR-029**: System MUST emit structured logs for all catalog operations
- **FR-030**: System MUST emit OpenTelemetry spans for all catalog operations (connect, create_namespace, create_table, vend_credentials, etc.)
- **FR-031**: OTel spans MUST include operation duration, status, catalog name, namespace, and table name attributes
- **FR-032**: OTel spans MUST NOT include credentials, PII, or sensitive data
- **FR-033**: System MUST support retry logic with configurable backoff for transient failures

**Configuration**

- **FR-034**: System MUST accept configuration through Pydantic models with validation
- **FR-035**: System MUST support credential configuration via environment variables or secret references
- **FR-036**: System MUST validate configuration at plugin initialization

### Key Entities

- **CatalogPlugin**: The abstract interface that all catalog implementations must satisfy. Defines operations for namespace management, table registration, and optional access control.

- **Namespace**: A logical container for tables. Supports hierarchical organization (parent.child.grandchild) and custom properties (location, owner, metadata). Can contain tables and child namespaces.

- **Table Registration**: Represents an Iceberg table's catalog entry. Contains table identifier, schema definition, storage location, partition specification, and custom properties.

- **Principal**: An identity (user or service account) that can be granted access to catalog resources. Used for access control in catalogs that support it.

- **Role**: A named collection of privileges that can be assigned to principals. Defines what operations (read, write, admin) are allowed on which resources (namespaces, tables).

- **Privilege Grant**: An assignment of privileges to a role for specific resources. Specifies the permission level and scope of access.

- **Vended Credentials**: Short-lived, scoped credentials returned by `vend_credentials()` for table access. Contains access key, secret key, session token (if applicable), and expiration timestamp. Scoped to specific tables and operations (READ/WRITE).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Plugin developers can implement a complete catalog adapter by following the ABC interface without external consultation in under 4 hours
- **SC-002**: Platform operators can connect to Polaris and perform first table registration within 15 minutes of configuration
- **SC-003**: Catalog operations (create namespace, register table, list tables) complete within 2 seconds under normal conditions
- **SC-004**: System recovers from temporary catalog unavailability within 30 seconds of service restoration
- **SC-005**: 100% of catalog operations produce structured logs suitable for observability integration
- **SC-006**: Access control configuration changes take effect within 5 seconds
- **SC-007**: Health checks accurately report catalog status within 1 second response time

## Assumptions

- Polaris server is deployed and accessible separately (not part of this feature scope)
- PyIceberg library provides the underlying catalog client operations
- OAuth2 identity provider is configured separately for authentication
- Plugin registry from Epic 1 is available for plugin discovery
- Catalog operations are synchronous (async patterns may be added in future iterations)

## Out of Scope

- Deployment and configuration of Polaris server itself
- AWS Glue adapter implementation (interface defined, implementation deferred)
- Hive Metastore adapter implementation (interface defined, implementation deferred)
- Data lineage tracking (covered by separate OpenLineage integration)
- Schema registry integration beyond Iceberg table schemas
- Multi-catalog federation (single catalog per deployment initially)
