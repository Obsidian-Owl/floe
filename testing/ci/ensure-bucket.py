#!/usr/bin/env python3
"""Ensure an S3-compatible bucket exists, creating it if necessary.

Usage: ensure-bucket.py <endpoint_url> <bucket_name>

Credentials are read from environment variables to avoid exposing
them via process arguments (visible in ``ps aux`` / ``/proc/*/cmdline``):
  MINIO_USER  - S3 access key ID (required)
  MINIO_PASS  - S3 secret access key (required)

Uses boto3 HeadBucket for authenticated detection (anonymous curl
returns 403 for both existing and non-existing buckets).
"""

from __future__ import annotations

import os
import sys

import boto3
from botocore.exceptions import ClientError


def main() -> None:
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <endpoint_url> <bucket>",
            file=sys.stderr,
        )
        print(
            "  Credentials: set MINIO_USER and MINIO_PASS environment variables",
            file=sys.stderr,
        )
        sys.exit(1)

    endpoint, bucket = sys.argv[1], sys.argv[2]
    user = os.environ.get("MINIO_USER", "")
    password = os.environ.get("MINIO_PASS", "")
    if not user or not password:
        print(
            "ERROR: MINIO_USER and MINIO_PASS environment variables are required",
            file=sys.stderr,
        )
        sys.exit(1)

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=user,
        aws_secret_access_key=password,
    )
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"Bucket {bucket} exists")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "404" or code == "NoSuchBucket":
            s3.create_bucket(Bucket=bucket)
            print(f"Bucket {bucket} created")
        else:
            raise


if __name__ == "__main__":
    main()
