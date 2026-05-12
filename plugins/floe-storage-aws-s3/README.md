# floe-storage-aws-s3

Native AWS S3 storage plugin for Floe.

This package emits secret-free `StorageDeploymentBinding` contracts for an
existing S3 bucket. It does not create buckets during compilation and does not
place AWS credential values in compiled artifacts.
