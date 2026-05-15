# floe-ingestion-dlt

> **Alpha release notice:** This `v0.1.0-alpha.1` package is for isolated evaluation only. Do not use Floe alpha packages with production data, production credentials, regulated workloads, customer-facing SLAs, or production-scale loads. Floe is distributed under Apache-2.0 on an "AS IS" basis; see the repository `LICENSE` for full terms.

dlt (data load tool) ingestion plugin for the floe data platform.

## Overview

This plugin implements the `IngestionPlugin` ABC from floe-core using
[dlt](https://dlthub.com/) as the ingestion framework. It supports loading
data from REST APIs, SQL databases, and filesystem sources into Iceberg
tables via the platform's Polaris REST catalog.

## Installation

```bash
uv pip install -e plugins/floe-ingestion-dlt
```

## Entry Point

Registered as `floe.ingestion = dlt` for automatic discovery by the
floe plugin registry.
