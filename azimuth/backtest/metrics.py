"""Performance metrics. ``docs/04_SPEC_PYTHON_CLI.md`` section 3.

CAGR, Sharpe, Sortino, MaxDD, Calmar, profit factor, expectancy.

TWO HARD RULES.

1. CLAUDE.md rule 2 -- nothing in this module may be called, and no number it
   produces may be reported, until ``azimuth parity`` passes at 1e-6 against the
   committed Pine fixture. A Python-only result describes a system that is not the
   one on the chart.

2. CLAUDE.md rule 4 and docs/11_FINDINGS.md finding 6 -- ``runs/N_trials.txt`` is
   incremented HERE, at the point a Sharpe is computed, not by the sweep driver.
   The sweep driver would miss single ``azimuth backtest`` runs, ablations, the
   equal-weight baseline and cross-instrument runs, all of which are trials that
   feed the Deflated Sharpe correction. N is the number of Sharpe values that have
   been LOOKED AT, not the number that were planned. It accumulates across the
   project's lifetime and is never reset.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

N_TRIALS_PATH = Path("runs/N_trials.txt")


def increment_n_trials(path: Path = N_TRIALS_PATH, by: int = 1) -> int:
    """Atomically increment the cumulative trial counter; return the new value.

    Called by :func:`sharpe`. Never reset. Never decrement.
    """
    raise NotImplementedError("M2 — CLAUDE.md rule 4, docs/11_FINDINGS.md finding 6")


def read_n_trials(path: Path = N_TRIALS_PATH) -> int:
    """Read the cumulative trial count that feeds the DSR."""
    raise NotImplementedError("M2 — docs/05_SPEC_VALIDATION.md section 5")


def sharpe(returns: pd.Series[float], periods_per_year: int) -> float:
    """Annualised Sharpe ratio. Increments the trial counter as a side effect."""
    raise NotImplementedError("M2 — docs/04_SPEC_PYTHON_CLI.md section 3")


def max_drawdown(equity: pd.Series[float]) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction."""
    raise NotImplementedError("M2 — docs/04_SPEC_PYTHON_CLI.md section 3")


def summarise(
    ledger: pd.DataFrame, equity: pd.Series[float], periods_per_year: int
) -> dict[str, float]:
    """Full metric set for a run: CAGR, Sharpe, Sortino, MaxDD, Calmar, PF, expectancy."""
    raise NotImplementedError("M2 — docs/04_SPEC_PYTHON_CLI.md section 3")
