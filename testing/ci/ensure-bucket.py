#!/usr/bin/env python3
"""Ensure an S3-compatible bucket exists, creating it if necessary.

Usage: ensure-bucket.py <user> <password> <endpoint_url> <bucket_name>

Uses boto3 HeadBucket for authenticated detection (anonymous curl
returns 403 for both existing and non-existing buckets).
"""

from __future__ import annotations

import sys

import boto3
from botocore.exceptions import ClientError


def main() -> None:
    if len(sys.argv) != 5:
        print(
            f"Usage: {sys.argv[0]} <user> <password> <endpoint_url> <bucket>",
            file=sys.stderr,
        )
        sys.exit(1)

    user, password, endpoint, bucket = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
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
