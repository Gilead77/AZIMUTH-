"""CLI surface tests.

``docs/04_SPEC_PYTHON_CLI.md`` section 4 lists nine commands. Every one must be
registered, and every unimplemented one must exit NON-ZERO -- a scripted pipeline
must not mistake a stub for a run that legitimately produced no output.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from azimuth.cli import app

runner = CliRunner()

COMMANDS = [
    "fetch",
    "signals",
    "backtest",
    "sweep",
    "validate",
    "ablate",
    "parity",
    "report",
    "watch",
]


def test_help_lists_every_spec_command():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in COMMANDS:
        assert command in result.stdout, f"`azimuth {command}` is missing from --help"


@pytest.mark.parametrize("command", COMMANDS)
def test_command_help_works(command: str):
    result = runner.invoke(app, [command, "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("fetch", ["--symbol", "BTC-USD", "--tf", "4h"]),
        ("signals", ["--symbol", "BTC-USD", "--tf", "4h"]),
        ("backtest", ["--symbol", "BTC-USD", "--tf", "4h"]),
        ("parity", ["--pine", "exports/x.csv"]),
        ("ablate", ["--symbol", "BTC-USD", "--tf", "4h"]),
        ("report", ["--run", "runs/x", "--out", "reports/x.html"]),
        ("watch", ["--symbols", "BTC-USD", "--tf", "4h"]),
    ],
)
def test_stub_exits_non_zero(command: str, args: list[str]):
    result = runner.invoke(app, [command, *args])
    assert result.exit_code != 0, f"`azimuth {command}` stub must not exit 0"


def test_validate_refuses_without_preregistration(tmp_path):
    """The gate is live from the first commit. It refuses before it reaches the
    not-implemented stub, which is the correct order of operations."""
    result = runner.invoke(app, ["validate", "--run", str(tmp_path)])
    assert result.exit_code == 3
    # The refusal goes to stderr, so a pipeline redirecting stdout still sees it.
    assert "PRE-REGISTRATION GATE: REFUSED" in result.stderr


def test_validate_refuses_the_shipped_template():
    """With no --preregistration flag the default is docs/09_PREREGISTRATION.md,
    which ships full of ____ blanks and must be refused as-is."""
    result = runner.invoke(app, ["validate", "--run", "runs/does-not-exist"])
    assert result.exit_code == 3
    assert "unfilled field" in result.stderr


def test_no_command_returns_help():
    result = runner.invoke(app, [])
    assert "AZIMUTH" in result.stdout
