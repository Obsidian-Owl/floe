#!/usr/bin/env python
"""Cleanup script to remove all test_ prefixed datasets from Cognee Cloud.

This script is useful for:
- Cleaning up orphaned test datasets from failed test runs
- Manual cleanup during development
- Resetting test state between test sessions

Usage:
    cd devtools/agent-memory
    uv run python scripts/cleanup_test_datasets.py

Requirements:
    - COGNEE_API_KEY environment variable set
    - OPENAI_API_KEY or ANTHROPIC_API_KEY set
"""

from __future__ import annotations

import asyncio
import sys


async def main() -> int:
    """Delete all test_ prefixed datasets and report results."""
    from agent_memory.cognee_client import CogneeClient
    from agent_memory.config import get_config

    print("Loading configuration...")
    config = get_config()

    print("Connecting to Cognee Cloud...")
    client = CogneeClient(config)

    # List existing datasets
    print("Listing datasets...")
    datasets = await client.list_datasets()

    test_datasets = [d for d in datasets if d.startswith("test_")]
    prod_datasets = [d for d in datasets if not d.startswith("test_")]

    print(f"\nFound {len(datasets)} total datasets:")
    print(f"  - {len(test_datasets)} test datasets (test_*)")
    print(f"  - {len(prod_datasets)} production datasets")

    if not test_datasets:
        print("\nNo test datasets to clean up.")
        return 0

    print(f"\nDeleting {len(test_datasets)} test datasets...")
    deleted = await client.delete_test_datasets()

    print(f"\nCleanup complete:")
    print(f"  - Deleted: {deleted}")
    print(f"  - Failed: {len(test_datasets) - deleted}")

    # List remaining datasets
    remaining = await client.list_datasets()
    remaining_test = [d for d in remaining if d.startswith("test_")]

    if remaining_test:
        print(f"\nWarning: {len(remaining_test)} test datasets remain:")
        for d in remaining_test:
            print(f"  - {d}")
        return 1

    print("\nAll test datasets cleaned up successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
