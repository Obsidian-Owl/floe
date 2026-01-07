# datacontract.yaml Reference

This document describes the `datacontract.yaml` file format used in floe. Contracts follow the **Open Data Contract Standard (ODCS)** v3.x specification.

## Overview

A data contract is a formal agreement between data producers and consumers that defines:
- Schema structure (models and elements)
- Service level agreements (SLAs)
- Ownership and governance
- Terms of use

## File Location

```
data-product/
├── floe.yaml          # Data product definition
├── datacontract.yaml          # Optional: explicit contract
├── models/
│   └── *.sql
└── tests/
```

When `datacontract.yaml` is present, it overrides auto-generated values from ports.

## Complete Schema

```yaml
# Required: ODCS API version
apiVersion: v3.0.2

# Required: Always "DataContract"
kind: DataContract

# Required: Unique contract identifier
name: sales-customer-360-customers

# Required: Semantic version (independent from data product)
version: 2.1.0

# Lifecycle status
status: active  # active | deprecated | sunset | retired

# ─────────────────────────────────────────────────────────────────
# Ownership
# ─────────────────────────────────────────────────────────────────

# Required: Contact email for contract owner
owner: sales-analytics@acme.com

# Optional: Business domain
domain: sales

# Optional: Team name
team: Sales Analytics Team

# ─────────────────────────────────────────────────────────────────
# Description
# ─────────────────────────────────────────────────────────────────

# Optional: Human-readable description
description: |
  Consolidated customer view combining CRM, transactions, and support data.
  Updated daily at 6am UTC.

# ─────────────────────────────────────────────────────────────────
# Models (Schema Definitions)
# ─────────────────────────────────────────────────────────────────

models:
  # Model name (table name)
  customers:
    description: Customer master data with 360-degree view

    # Column definitions
    elements:
      customer_id:
        type: string
        required: true
        primaryKey: true
        unique: true
        description: Unique customer identifier (UUID)

      email:
        type: string
        required: true
        format: email
        unique: true
        classification: pii
        description: Primary email address

      name:
        type: string
        required: true
        classification: pii
        description: Full legal name

      phone:
        type: string
        required: false
        format: phone
        classification: pii
        description: Primary phone number

      created_at:
        type: timestamp
        required: true
        description: Account creation timestamp

      updated_at:
        type: timestamp
        required: true
        description: Last update timestamp

      lifetime_value:
        type: decimal
        required: false
        description: Calculated customer lifetime value

      segment:
        type: string
        required: false
        enum: [enterprise, mid-market, smb, consumer]
        description: Customer segment classification

# ─────────────────────────────────────────────────────────────────
# SLA Properties
# ─────────────────────────────────────────────────────────────────

slaProperties:
  # Data freshness requirement
  freshness:
    value: "PT6H"           # ISO 8601 duration (6 hours)
    element: updated_at     # Column to check for freshness

  # Availability target
  availability:
    value: "99.9%"          # Percentage uptime

  # Quality thresholds
  quality:
    completeness: "99%"     # Percentage of non-null required fields
    uniqueness: "100%"      # For primary key columns
    accuracy: "95%"         # Optional accuracy score

# ─────────────────────────────────────────────────────────────────
# Terms and Governance
# ─────────────────────────────────────────────────────────────────

terms:
  usage: "Internal analytics and reporting only"
  retention: "7 years per data retention policy"
  pii_handling: "Encryption at rest required, no export without approval"
  limitations: "Not approved for ML training"

# ─────────────────────────────────────────────────────────────────
# Deprecation (when status != active)
# ─────────────────────────────────────────────────────────────────

deprecation:
  announced: "2026-01-03"
  sunset_date: "2026-02-03"
  replacement: sales-customers-v4
  migration_guide: https://wiki.acme.com/migrate-customers-v4
  reason: "Replacing with unified customer model"

# ─────────────────────────────────────────────────────────────────
# Tags
# ─────────────────────────────────────────────────────────────────

tags:
  - customer-data
  - gold-layer
  - sales-domain
  - pii

# ─────────────────────────────────────────────────────────────────
# Links
# ─────────────────────────────────────────────────────────────────

links:
  documentation: https://wiki.acme.com/data/customer-360
  source_code: https://github.com/acme/data-products/customer-360
  dashboard: https://metabase.acme.com/dashboard/123
```

## Field Reference

### Root Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `apiVersion` | Yes | string | ODCS version (e.g., `v3.0.2`) |
| `kind` | Yes | string | Always `DataContract` |
| `name` | Yes | string | Unique contract identifier |
| `version` | Yes | string | Semantic version (Major.Minor.Patch) |
| `status` | No | enum | `active`, `deprecated`, `sunset`, `retired` |
| `owner` | Yes | string | Contact email |
| `domain` | No | string | Business domain |
| `team` | No | string | Team name |
| `description` | No | string | Human-readable description |
| `models` | Yes | object | Schema definitions |
| `slaProperties` | No | object | SLA definitions |
| `terms` | No | object | Terms of use |
| `deprecation` | No | object | Deprecation info (when deprecated) |
| `tags` | No | array | Tags for categorization |
| `links` | No | object | Related URLs |

### Element Types

| Type | Description | Example |
|------|-------------|---------|
| `string` | Text data | `"hello"` |
| `int` | Integer | `42` |
| `long` | Long integer | `9223372036854775807` |
| `float` | Floating point | `3.14` |
| `double` | Double precision | `3.141592653589793` |
| `decimal` | Exact decimal | `123.45` |
| `boolean` | True/false | `true` |
| `date` | Date only | `2026-01-03` |
| `timestamp` | Date and time | `2026-01-03T10:15:30Z` |
| `bytes` | Binary data | Base64 encoded |
| `array` | List of values | `[1, 2, 3]` |
| `object` | Nested structure | `{"key": "value"}` |

### Element Formats

| Format | Description | Example |
|--------|-------------|---------|
| `email` | Email address | `user@example.com` |
| `uri` | URI/URL | `https://example.com` |
| `uuid` | UUID | `550e8400-e29b-41d4-a716-446655440000` |
| `phone` | Phone number | `+1-555-123-4567` |
| `date` | ISO date | `2026-01-03` |
| `date-time` | ISO datetime | `2026-01-03T10:15:30Z` |
| `ipv4` | IPv4 address | `192.168.1.1` |
| `ipv6` | IPv6 address | `2001:0db8:85a3::8a2e:0370:7334` |

### Classification Levels

| Classification | Description |
|----------------|-------------|
| `public` | Publicly available data |
| `internal` | Internal use only |
| `confidential` | Restricted access |
| `pii` | Personally identifiable information |
| `phi` | Protected health information |
| `sensitive` | Sensitive business data |
| `restricted` | Highly restricted |

### SLA Duration Format

SLA durations use ISO 8601 format:

| Duration | Meaning |
|----------|---------|
| `PT15M` | 15 minutes |
| `PT1H` | 1 hour |
| `PT6H` | 6 hours |
| `P1D` | 1 day |
| `P7D` | 7 days |

## Minimal Example

```yaml
apiVersion: v3.0.2
kind: DataContract
name: simple-users
version: 1.0.0
owner: data-team@example.com

models:
  users:
    elements:
      id:
        type: string
        primaryKey: true
      email:
        type: string
        format: email
```

## Full Example with All Features

```yaml
apiVersion: v3.0.2
kind: DataContract
name: ecommerce-orders
version: 3.2.1

owner: commerce-analytics@acme.com
domain: commerce
team: Commerce Data Team

description: |
  Order data from the e-commerce platform. Includes all completed,
  pending, and cancelled orders. Updated every 15 minutes.

status: active

models:
  orders:
    description: E-commerce order records
    elements:
      order_id:
        type: string
        required: true
        primaryKey: true
        unique: true
        format: uuid
        description: Unique order identifier

      customer_id:
        type: string
        required: true
        description: Reference to customer

      order_date:
        type: timestamp
        required: true
        description: When order was placed

      status:
        type: string
        required: true
        enum: [pending, confirmed, shipped, delivered, cancelled]
        description: Current order status

      total_amount:
        type: decimal
        required: true
        description: Total order value in USD

      items:
        type: array
        required: true
        description: Line items in the order

  order_items:
    description: Individual line items within orders
    elements:
      item_id:
        type: string
        required: true
        primaryKey: true

      order_id:
        type: string
        required: true
        description: Parent order reference

      product_id:
        type: string
        required: true

      quantity:
        type: int
        required: true

      unit_price:
        type: decimal
        required: true

slaProperties:
  freshness:
    value: "PT15M"
    element: updated_at
  availability:
    value: "99.95%"
  quality:
    completeness: "99.9%"
    uniqueness: "100%"

terms:
  usage: "Analytics and reporting"
  retention: "3 years"
  limitations: "No direct customer contact from this data"

tags:
  - orders
  - commerce
  - gold-layer
  - revenue

links:
  documentation: https://wiki.acme.com/data/orders
  dashboard: https://looker.acme.com/orders
```

## Validation

### Using floe CLI

```bash
# Validate contract syntax
floe contract validate datacontract.yaml

# Lint for best practices
floe contract lint datacontract.yaml

# Check against live data
floe contract test datacontract.yaml --connection prod
```

### Using datacontract-cli

```bash
# Install
pip install datacontract-cli

# Validate
datacontract lint datacontract.yaml

# Test against data source
datacontract test datacontract.yaml
```

## Versioning Rules

| Change | Version Bump | Example |
|--------|--------------|---------|
| Remove element | MAJOR | Delete `email` field |
| Change element type | MAJOR | `id: int` → `id: string` |
| Make optional required | MAJOR | `phone: optional` → `phone: required` |
| Add required element | MAJOR | New `ssn` with `required: true` |
| Relax SLA | MAJOR | Freshness 4h → 8h |
| Add optional element | MINOR | New `nickname` field |
| Make required optional | MINOR | `phone: required` → `phone: optional` |
| Stricter SLA | MINOR | Freshness 6h → 4h |
| Update description | PATCH | Documentation changes |
| Add/change tags | PATCH | Metadata changes |

## Related Documents

- [Data Contracts Architecture](../architecture/data-contracts.md)
- [ADR-0026: Data Contract Architecture](../architecture/adr/0026-data-contract-architecture.md)
- [ADR-0027: ODCS Standard Adoption](../architecture/adr/0027-odcs-standard-adoption.md)
- [Contract Versioning Guide](../guides/contract-versioning.md)
- [ODCS Specification](https://datacontract.com/spec/odcs)
