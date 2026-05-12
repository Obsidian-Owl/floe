# floe-catalog-glue

Native AWS Glue catalog plugin for Floe.

This package emits secret-free `CatalogDeploymentBinding` contracts for AWS
Glue and delegates runtime catalog access to PyIceberg's Glue catalog. It does
not place AWS credential values in compiled artifacts.
