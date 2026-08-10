#!/usr/bin/env python3
"""Assert ``runs/N_trials.txt`` never decreases.

CLAUDE.md rule 4: the cumulative trial counter accumulates across the project's
lifetime and is never reset. It feeds the Deflated Sharpe Ratio
(``docs/05_SPEC_VALIDATION.md`` section 5), where under-counting N makes a result
look more significant than it is.

A commit that lowers this number is a bug, not a cleanup. Run in CI against the
value on the merge base.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

N_TRIALS = Path("runs/N_trials.txt")


def _parse(text: str, source: str) -> int:
    stripped = text.strip()
    if not stripped.isdigit():
        raise SystemExit(f"{source}: expected a single non-negative integer, got {stripped!r}")
    return int(stripped)


def previous_value(ref: str = "origin/main") -> int | None:
    """The counter's value at ``ref``, or None if it is unavailable there."""
    try:
        out = subprocess.run(
            ["git", "show", f"{ref}:{N_TRIALS.as_posix()}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return _parse(out.stdout, f"{ref}:{N_TRIALS}")


def main() -> int:
    if not N_TRIALS.is_file():
        print(f"FAIL: {N_TRIALS} is missing. It is permanent project state.", file=sys.stderr)
        return 1

    current = _parse(N_TRIALS.read_text(encoding="utf-8"), str(N_TRIALS))
    previous = previous_value()

    if previous is None:
        print(f"OK: N_trials = {current} (no baseline to compare against)")
        return 0

    if current < previous:
        print(
            f"FAIL: N_trials decreased {previous} -> {current}.\n"
            "CLAUDE.md rule 4: this counter is never reset. Under-counting N inflates the "
            "Deflated Sharpe Ratio and makes a noise result look significant.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: N_trials = {current} (was {previous})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
