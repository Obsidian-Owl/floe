"""Structural tests for live AWS provider validation IAM contracts."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_IAM_TF_PATH = _REPO_ROOT / "infra" / "aws-provider-tests" / "iam.tf"
_READINESS_SCRIPT_PATH = _REPO_ROOT / "scripts" / "aws-provider-test-readiness.sh"


def _read_iam_tf() -> str:
    """Return the AWS provider test IAM OpenTofu module contents."""
    return _IAM_TF_PATH.read_text()


def _read_readiness_script() -> str:
    """Return the AWS provider test readiness script contents."""
    return _READINESS_SCRIPT_PATH.read_text()


@pytest.mark.requirement("LIVE-VALIDATION")
def test_glue_database_delete_policy_covers_child_resources() -> None:
    """PyIceberg Glue namespace deletion authorizes DeleteDatabase on child ARNs."""
    iam_tf = _read_iam_tf()

    database_statement = re.search(
        r'sid = "ManageProviderTestGlueDatabases"(?P<body>.*?)^\s*}\n',
        iam_tf,
        re.DOTALL | re.MULTILINE,
    )

    assert database_statement is not None
    body = database_statement.group("body")
    assert '"glue:DeleteDatabase"' in body
    assert (
        '"arn:aws:glue:${var.aws_region}:${local.account_id}:table/${var.glue_database_prefix}*/*"'
        in body
    )
    assert (
        '"arn:aws:glue:${var.aws_region}:${local.account_id}:userDefinedFunction/${var.glue_database_prefix}*/*"'
        in body
    )


@pytest.mark.requirement("LIVE-VALIDATION")
def test_readiness_policy_check_requires_delete_database_on_child_resources() -> None:
    """Readiness must catch the IAM gap that only appears on non-empty Glue namespaces."""
    script = _read_readiness_script()
    expected_udf_resource = (
        'resources(.) | index("arn:aws:glue:\\($region):\\($account):'
        'userDefinedFunction/\\($glue_prefix)*/*")'
    )

    assert 'actions(.) | index("glue:DeleteDatabase")' in script
    assert (
        'resources(.) | index("arn:aws:glue:\\($region):\\($account):table/\\($glue_prefix)*/*")'
        in script
    )
    assert expected_udf_resource in script
