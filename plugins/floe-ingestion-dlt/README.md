# floe-ingestion-dlt

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
