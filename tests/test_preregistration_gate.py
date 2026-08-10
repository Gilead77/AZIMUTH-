"""Pre-registration gate tests.

``docs/04_SPEC_PYTHON_CLI.md`` section 4 and CLAUDE.md rule 3: ``azimuth validate``
must refuse to run unless the pre-registration exists, is filled in, and its
SHA-256 was recorded in the run manifest before the sweep ran. Hard error, no
bypass flag.

The last test in this file asserts that no bypass exists. If someone adds one, it
fails.
"""

from __future__ import annotations

import ast
import inspect
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from azimuth.validate import gate
from azimuth.validate.gate import PreRegistrationError, assert_preregistration_valid

FILLED = """# Pre-Registration

**Registration ID:** AZIMUTH-PR-001
**Date:** 2026-08-10

## 1. Hypothesis
H1: On BTC-USD at 1H the composite generates entries with positive expectancy
net of 15 bps, exceeding a matched random-entry benchmark at the 95th percentile.

## 9. Commitment to publication
[x] I commit to writing up the result in results/ regardless of outcome,
including a null result.
"""


def _write_manifest(
    path: Path,
    *,
    prereg_path: Path,
    sha: str,
    recorded_at: datetime,
    sweep_started_at: datetime,
) -> None:
    path.write_text(
        json.dumps(
            {
                "preregistration": {
                    "path": str(prereg_path),
                    "sha256": sha,
                    "recorded_at": recorded_at.isoformat(),
                },
                "sweep_started_at": sweep_started_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def valid_run(tmp_path: Path) -> tuple[Path, Path]:
    """A pre-registration and manifest that should pass the gate."""
    prereg = tmp_path / "09_PREREGISTRATION.md"
    prereg.write_text(FILLED, encoding="utf-8")

    recorded = datetime(2026, 8, 10, 12, 0, 0)
    _write_manifest(
        tmp_path / "manifest.json",
        prereg_path=prereg,
        sha=gate.file_sha256(prereg),
        recorded_at=recorded,
        sweep_started_at=recorded + timedelta(minutes=5),
    )
    return prereg, tmp_path / "manifest.json"


def test_valid_registration_passes(valid_run):
    prereg, manifest = valid_run
    assert assert_preregistration_valid(prereg, manifest) == gate.file_sha256(prereg)


def test_missing_file_is_refused(tmp_path: Path):
    with pytest.raises(PreRegistrationError, match="not found"):
        assert_preregistration_valid(tmp_path / "nope.md", tmp_path / "manifest.json")


def test_unfilled_blanks_are_refused(tmp_path: Path, valid_run):
    """The shipped docs/09 template is full of ____ blanks. A partially completed
    registration registers nothing."""
    _, manifest = valid_run
    prereg = tmp_path / "blank.md"
    prereg.write_text("**Date:** ____________\n\n results/ \n", encoding="utf-8")

    with pytest.raises(PreRegistrationError, match="unfilled field"):
        assert_preregistration_valid(prereg, manifest)


def test_shipped_template_is_refused_as_is():
    """The real docs/09_PREREGISTRATION.md, unedited, must not pass the gate."""
    shipped = Path("docs/09_PREREGISTRATION.md")
    if not shipped.is_file():  # pragma: no cover
        pytest.skip("docs/09_PREREGISTRATION.md not present")
    with pytest.raises(PreRegistrationError):
        assert_preregistration_valid(shipped, Path("runs/nonexistent/manifest.json"))


def test_missing_publication_commitment_is_refused(tmp_path: Path, valid_run):
    """docs/09 section 9. A null result is a successful run (CLAUDE.md rule 5) and
    the commitment to report it is part of the registration."""
    _, manifest = valid_run
    prereg = tmp_path / "no_commit.md"
    prereg.write_text("# Registration\n\nH1: something falsifiable.\n", encoding="utf-8")

    with pytest.raises(PreRegistrationError, match="commitment to publish"):
        assert_preregistration_valid(prereg, manifest)


def test_edited_after_registration_is_refused(valid_run):
    """The whole point: the hypothesis cannot be edited after seeing results."""
    prereg, manifest = valid_run
    prereg.write_text(FILLED + "\n(edited to match the results)\n", encoding="utf-8")

    with pytest.raises(PreRegistrationError, match="SHA-256 mismatch"):
        assert_preregistration_valid(prereg, manifest)


def test_registered_after_the_sweep_is_refused(tmp_path: Path):
    """Post-registration provides no protection against fitting the hypothesis to
    the results (docs/05 section 0 orders registration first)."""
    prereg = tmp_path / "09.md"
    prereg.write_text(FILLED, encoding="utf-8")

    sweep_start = datetime(2026, 8, 10, 12, 0, 0)
    _write_manifest(
        tmp_path / "manifest.json",
        prereg_path=prereg,
        sha=gate.file_sha256(prereg),
        recorded_at=sweep_start + timedelta(hours=3),  # after the fact
        sweep_started_at=sweep_start,
    )

    with pytest.raises(PreRegistrationError, match="AFTER the sweep"):
        assert_preregistration_valid(prereg, tmp_path / "manifest.json")


def test_missing_manifest_is_refused(tmp_path: Path):
    prereg = tmp_path / "09.md"
    prereg.write_text(FILLED, encoding="utf-8")
    with pytest.raises(PreRegistrationError, match="No run manifest"):
        assert_preregistration_valid(prereg, tmp_path / "absent" / "manifest.json")


def test_manifest_without_preregistration_block_is_refused(tmp_path: Path):
    prereg = tmp_path / "09.md"
    prereg.write_text(FILLED, encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"git_sha": "abc"}), encoding="utf-8")

    with pytest.raises(PreRegistrationError, match="no 'preregistration' block"):
        assert_preregistration_valid(prereg, tmp_path / "manifest.json")


def test_gate_has_no_bypass():
    """CLAUDE.md rule 3: 'Do not add a bypass flag. Do not temporarily disable it.'

    Asserted against the AST rather than the raw text, so that prose explaining
    there is no bypass does not trip it and an actual bypass cannot hide in a
    docstring-free helper.
    """
    tree = ast.parse(Path(gate.__file__).read_text(encoding="utf-8"))

    banned_params = {"force", "bypass", "skip", "skip_gate", "no_gate", "override", "strict"}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            args = node.args
            names = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
            offending = names & banned_params
            assert not offending, (
                f"{node.name}() takes {sorted(offending)}. The pre-registration gate is "
                "unconditional (CLAUDE.md rule 3) -- it accepts no parameter that could "
                "weaken or skip it."
            )

    # No environment-variable escape hatch. The module does not import os at all.
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "os" not in imported, "gate.py must not read the environment -- no env-var bypass"
    assert "warnings" not in imported, "gate failures are errors, never warnings"


def test_gate_signature_is_exactly_two_paths():
    """No third argument may be added that could soften the check."""
    params = list(inspect.signature(assert_preregistration_valid).parameters)
    assert params == ["preregistration_path", "manifest_path"]


def test_every_gate_failure_path_raises():
    """Each check must raise, not return a falsy value a caller could ignore."""
    tree = ast.parse(Path(gate.__file__).read_text(encoding="utf-8"))
    func = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "assert_preregistration_valid"
    )
    raises = [n for n in ast.walk(func) if isinstance(n, ast.Raise)]
    assert len(raises) >= 4, (
        f"expected at least 4 raise statements (exists / filled-in / hash / ordering), "
        f"found {len(raises)}"
    )


def test_cli_exits_non_zero_when_the_gate_refuses():
    """The CLI may format the error, but must not catch it and carry on."""
    cli = Path("azimuth/cli.py").read_text(encoding="utf-8")
    assert "PreRegistrationError" in cli
    assert "typer.Exit(code=3)" in cli, "validate must exit non-zero when the gate refuses"
