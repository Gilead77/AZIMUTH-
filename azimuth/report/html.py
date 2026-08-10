"""Single self-contained HTML report. ``docs/04_SPEC_PYTHON_CLI.md`` section 3.

Must prominently feature, per ``docs/05_SPEC_VALIDATION.md``:

* the break-even cost (section 3) -- if it is below the realistic cost, the system
  is dead regardless of the Sharpe;
* the parameter-surface plateau plot (criterion 7) -- a sharp spike is the
  signature of an overfit, a broad plateau the signature of a real effect;
* N and the resulting DSR, so no Sharpe is ever shown without its correction.
"""

from __future__ import annotations

from pathlib import Path


def render(run_dir: Path, out: Path) -> Path:
    """Render a run directory to one self-contained HTML file."""
    raise NotImplementedError("M3 — docs/04_SPEC_PYTHON_CLI.md section 3")
