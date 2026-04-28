"""Render Helm value overrides for the Dagster demo image.

The chart's test values use YAML anchors, but Helm override merging happens
after YAML anchor expansion. This helper writes every concrete Dagster image
consumer so CI and DevPod validation use the exact image that was built and
loaded into Kind.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import yaml


def _validate_non_empty(name: str, value: str) -> str:
    value = value.strip()
    if not value:
        raise SystemExit(f"{name} cannot be empty")
    return value


def _image_values(repository: str, tag: str, pull_policy: str) -> dict[str, str]:
    return {
        "repository": repository,
        "tag": tag,
        "pullPolicy": pull_policy,
    }


def render_values(repository: str, tag: str, pull_policy: str) -> str:
    """Return YAML overrides for every Dagster image consumer."""
    repository = _validate_non_empty("repository", repository)
    tag = _validate_non_empty("tag", tag)
    pull_policy = _validate_non_empty("pull_policy", pull_policy)

    values: dict[str, Any] = {
        "dagsterDemoImage": _image_values(repository, tag, pull_policy),
        "dagster": {
            "dagsterWebserver": {
                "image": _image_values(repository, tag, pull_policy),
            },
            "dagsterDaemon": {
                "image": _image_values(repository, tag, pull_policy),
            },
            "runLauncher": {
                "config": {
                    "k8sRunLauncher": {
                        "image": _image_values(repository, tag, pull_policy),
                        "imagePullPolicy": pull_policy,
                    },
                },
            },
        },
    }
    return yaml.safe_dump(values, sort_keys=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("FLOE_DEMO_IMAGE_REPOSITORY", ""))
    parser.add_argument("--tag", default=os.environ.get("FLOE_DEMO_IMAGE_TAG", ""))
    parser.add_argument(
        "--pull-policy",
        default=os.environ.get("FLOE_DEMO_IMAGE_PULL_POLICY", "Never"),
    )
    args = parser.parse_args()
    sys.stdout.write(render_values(args.repository, args.tag, args.pull_policy))


if __name__ == "__main__":
    main()
