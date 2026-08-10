"""Pre-registration gate.

Implements the guard rail in ``docs/04_SPEC_PYTHON_CLI.md`` section 4 and the
order of operations in ``docs/05_SPEC_VALIDATION.md`` section 0.

``azimuth validate`` must refuse to run unless ``docs/09_PREREGISTRATION.md``
exists, is filled in, and its SHA-256 was recorded in the run manifest *before*
the sweep executed.

CLAUDE.md rule 3 is explicit: this is a hard error, not a warning. There is no
bypass flag and none may be added -- not behind an environment variable, not
"temporarily" for debugging. The entire value of a pre-registration is that the
hypothesis cannot be edited after results are visible; a bypass makes the
document decorative.

This module is deliberately dependency-free beyond the standard library so the
gate cannot fail open because an optional import broke.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

__all__ = [
    "PreRegistrationError",
    "assert_preregistration_valid",
    "file_sha256",
    "find_unfilled_placeholders",
]

_PLACEHOLDER_RE = re.compile(r"_{4,}")
"""``docs/09_PREREGISTRATION.md`` ships with ``____`` blanks. Any remaining run of
four or more underscores means a field was never filled in."""

_REQUIRED_COMMITMENT = "results/"
"""Section 9 commits to writing up the result regardless of outcome."""


class PreRegistrationError(RuntimeError):
    """Raised when the pre-registration gate refuses to let validation proceed.

    Always fatal. Callers must not catch this to continue -- catch it only to
    format the message for the user, then exit non-zero.
    """


def file_sha256(path: str | Path) -> str:
    """SHA-256 of a file's bytes, lowercase hex.

    Hashes bytes rather than decoded text so a line-ending change is a different
    hash. That is intended: the registered artefact is the file as committed.
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_unfilled_placeholders(text: str) -> list[str]:
    """Return the lines of ``text`` still containing ``____`` blanks."""
    return [
        line.strip()
        for line in text.splitlines()
        if _PLACEHOLDER_RE.search(line) and not line.lstrip().startswith(">")
    ]


@dataclass(frozen=True)
class ManifestRecord:
    """The pre-registration fields a run manifest must carry.

    Written by ``azimuth sweep`` at the moment the sweep starts, per
    ``docs/04_SPEC_PYTHON_CLI.md`` section 8.
    """

    path: str
    sha256: str
    recorded_at: datetime
    sweep_started_at: datetime


def _parse_manifest(manifest_path: Path) -> ManifestRecord:
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PreRegistrationError(
            f"No run manifest at {manifest_path}.\n"
            "Every run writes manifest.json (docs/04 section 8). Without it there is no "
            "record that a hypothesis was registered before the sweep, so validation "
            "cannot proceed."
        ) from exc
    except json.JSONDecodeError as exc:
        raise PreRegistrationError(f"{manifest_path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise PreRegistrationError(f"{manifest_path}: expected a JSON object at the top level")

    prereg = raw.get("preregistration")
    if not isinstance(prereg, dict):
        raise PreRegistrationError(
            f"{manifest_path} has no 'preregistration' block.\n"
            "The sweep must record the pre-registration path, its SHA-256 and the "
            "recording time BEFORE it runs (docs/05 section 0 step 1). A manifest without "
            "it describes a sweep whose hypothesis is unknown."
        )

    missing = [k for k in ("path", "sha256", "recorded_at") if k not in prereg]
    if missing:
        raise PreRegistrationError(f"{manifest_path}: preregistration block is missing {missing}.")
    if "sweep_started_at" not in raw:
        raise PreRegistrationError(
            f"{manifest_path}: missing 'sweep_started_at'. Without it the gate cannot "
            "verify the hypothesis was registered before results existed."
        )

    try:
        recorded_at = datetime.fromisoformat(str(prereg["recorded_at"]))
        sweep_started_at = datetime.fromisoformat(str(raw["sweep_started_at"]))
    except ValueError as exc:
        raise PreRegistrationError(f"{manifest_path}: timestamps must be ISO-8601: {exc}") from exc

    return ManifestRecord(
        path=str(prereg["path"]),
        sha256=str(prereg["sha256"]).lower(),
        recorded_at=recorded_at,
        sweep_started_at=sweep_started_at,
    )


def assert_preregistration_valid(
    preregistration_path: str | Path,
    manifest_path: str | Path,
) -> str:
    """Verify the pre-registration gate. Returns the verified SHA-256.

    Four checks, all fatal (``docs/04_SPEC_PYTHON_CLI.md`` section 4):

    1. the pre-registration file exists;
    2. it is filled in -- no ``____`` blanks remain, and the publication
       commitment in section 9 is present;
    3. its current SHA-256 matches the one recorded in the run manifest, so the
       document has not been edited since registration;
    4. it was recorded *before* the sweep started, so the hypothesis cannot have
       been written to fit results.

    Raises:
        PreRegistrationError: on any failure. There is no bypass.
    """
    prereg = Path(preregistration_path)
    manifest = Path(manifest_path)

    # 1. exists
    if not prereg.is_file():
        raise PreRegistrationError(
            f"Pre-registration file not found: {prereg}\n"
            "docs/05_SPEC_VALIDATION.md section 0 step 1: fill it in, commit it, record its "
            "SHA-256 -- before the sweep. Validation cannot proceed without it."
        )

    text = prereg.read_text(encoding="utf-8")

    # 2. filled in
    blanks = find_unfilled_placeholders(text)
    if blanks:
        shown = "\n  ".join(blanks[:10])
        more = f"\n  ... and {len(blanks) - 10} more" if len(blanks) > 10 else ""
        raise PreRegistrationError(
            f"{prereg} still has {len(blanks)} unfilled field(s):\n  {shown}{more}\n"
            "A partially completed pre-registration registers nothing. Fill every blank, "
            "commit, then re-run the sweep."
        )
    if _REQUIRED_COMMITMENT not in text:
        raise PreRegistrationError(
            f"{prereg} is missing the section 9 commitment to publish the result in "
            "results/ regardless of outcome. A null result is a successful run of this "
            "project (CLAUDE.md rule 5) and the commitment to report it is part of the "
            "registration."
        )

    # 3. hash matches what was recorded
    record = _parse_manifest(manifest)
    actual = file_sha256(prereg)
    if actual != record.sha256:
        raise PreRegistrationError(
            f"Pre-registration SHA-256 mismatch.\n"
            f"  recorded in manifest : {record.sha256}\n"
            f"  file on disk now     : {actual}\n"
            f"  file                 : {prereg}\n"
            "The pre-registration has been modified since the sweep ran. docs/09 section 8: "
            "no configurations, components or instruments may be added after seeing results. "
            "Anything further requires a NEW registration ID and resets the interpretation -- "
            "start AZIMUTH-PR-002 rather than editing this one."
        )

    # 4. registered before the sweep, not after
    if record.recorded_at > record.sweep_started_at:
        raise PreRegistrationError(
            f"Pre-registration was recorded AFTER the sweep started.\n"
            f"  registered   : {record.recorded_at.isoformat()}\n"
            f"  sweep started: {record.sweep_started_at.isoformat()}\n"
            "This is post-registration, which provides no protection against fitting the "
            "hypothesis to the results. The run is not usable for validation."
        )

    return actual
