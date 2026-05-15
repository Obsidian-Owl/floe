# floe-catalog-glue

> **Alpha release notice:** This `v0.1.0-alpha.1` package is for isolated evaluation only. Do not use Floe alpha packages with production data, production credentials, regulated workloads, customer-facing SLAs, or production-scale loads. Floe is distributed under Apache-2.0 on an "AS IS" basis; see the repository `LICENSE` for full terms.

Native AWS Glue catalog plugin for Floe.

This package emits secret-free `CatalogDeploymentBinding` contracts for AWS
Glue and delegates runtime catalog access to PyIceberg's Glue catalog. It does
not place AWS credential values in compiled artifacts.
