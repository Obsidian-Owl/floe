"""Tests for the Customer 360 demo runner CLI."""

from __future__ import annotations

import pytest
import run_customer_360_demo


@pytest.mark.requirement("alpha-demo")
@pytest.mark.parametrize(
    ("env_name", "expected_argument"),
    [
        ("FLOE_DEMO_RUN_TIMEOUT_SECONDS", "--timeout-seconds"),
        ("FLOE_DEMO_RUN_POLL_INTERVAL_SECONDS", "--poll-interval-seconds"),
    ],
)
def test_parser_reports_invalid_env_float_defaults_through_argparse(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    env_name: str,
    expected_argument: str,
) -> None:
    """Parser reports invalid env-sourced float defaults without a Python traceback."""
    monkeypatch.setenv(env_name, "not-a-float")
    parser = run_customer_360_demo.build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])

    assert exc_info.value.code == 2
    expected_error = f"argument {expected_argument}: invalid float value: 'not-a-float'"
    assert expected_error in capsys.readouterr().err


@pytest.mark.requirement("alpha-demo")
def test_parser_returns_float_defaults_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser converts valid env-sourced defaults into float runtime values."""
    monkeypatch.setenv("FLOE_DEMO_RUN_TIMEOUT_SECONDS", "42.5")
    monkeypatch.setenv("FLOE_DEMO_RUN_POLL_INTERVAL_SECONDS", "1.25")

    args = run_customer_360_demo.build_parser().parse_args([])

    assert isinstance(args.timeout_seconds, float)
    assert isinstance(args.poll_interval_seconds, float)
    assert args.timeout_seconds == 42.5
    assert args.poll_interval_seconds == 1.25


@pytest.mark.requirement("alpha-demo")
def test_parser_prefers_cli_float_values_over_invalid_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit CLI float values override invalid env defaults during parsing."""
    monkeypatch.setenv("FLOE_DEMO_RUN_TIMEOUT_SECONDS", "not-a-float")
    parser = run_customer_360_demo.build_parser()

    args = parser.parse_args(["--timeout-seconds", "10"])

    assert args.timeout_seconds == 10.0
