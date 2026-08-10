"""Pine <-> Python parity harness. Implements ``docs/06_PARITY_TESTS.md``.

THE GATE. If Pine and Python disagree, every validation result is worthless -- you
would be validating a different system from the one that trades. Parity is a gate,
not a nice-to-have (docs/06 preamble, CLAUDE.md rule 2).

Assertions (docs/06 section 2):

=================================  =========  ==============================
Series                             Tolerance  Notes
=================================  =========  ==============================
``x_ribbon``                       1e-6       EMA seeding must match
``x_bb``, ``x_pctb``, ``x_bwpct``  1e-6       stdev is population, ddof=0
``x_rsi``                          1e-5       RMA seeding differs in burn-in
``x_htf``                          see below  finding 11
``x_corr``                         1e-5
``x_er``, ``x_adx``                1e-5
``x_state``                        exact      integer, bar for bar
Signal bar indices                 exact      set equality of trigger times
=================================  =========  ==============================

Burn-in: discard the first ``max(233, 200, 60) + 50 = 283`` bars before comparing.

docs/11_FINDINGS.md finding 11 -- docs/06 sets ``x_htf`` to "exact", but
``htfScore = clip(0.6*h1 + 0.4*h2)`` with each ``h`` in {-1, -1/3, +1/3, +1}, and
0.6*(1/3) is not representable in binary64 (it evaluates to 0.19999999999999998).
Strict float equality fails on CORRECT code. Compare at 1e-9, plus the assertion
"exact" was reaching for: the set of distinct values must have cardinality <= 16
and each must lie within 1e-9 of the lattice
``{0.6a + 0.4b : a, b in {-1, -1/3, 1/3, 1}}`` after clipping. That catches genuine
alignment bugs, which produce off-lattice values, without failing on float noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from azimuth.config.schema import AzimuthConfig

BURN_IN_BARS = 283
"""max(233, 200, 60) + 50 (docs/06 section 2)."""

TOLERANCES: dict[str, float] = {
    "x_ribbon": 1e-6,
    "x_bb": 1e-6,
    "x_pctb": 1e-6,
    "x_bwpct": 1e-6,
    "x_rsi": 1e-5,
    "x_htf": 1e-9,  # finding 11: "exact" fails on correct code
    "x_corr": 1e-5,
    "x_er": 1e-5,
    "x_adx": 1e-5,
    "x_state": 0.0,  # integer state machine, exact
}


@dataclass(frozen=True)
class ParityResult:
    """Per-series comparison outcome."""

    series: str
    tolerance: float
    max_abs_diff: float
    n_compared: int
    passed: bool


def load_pine_export(path: str | Path) -> pd.DataFrame:
    """Parse a TradingView 'Export chart data' CSV into a frame of ``x_*`` series."""
    raise NotImplementedError("M1 — docs/06_PARITY_TESTS.md section 1")


def compare(pine: pd.DataFrame, python: pd.DataFrame, tol: float = 1e-6) -> list[ParityResult]:
    """Compare every ``x_*`` series after the burn-in; return per-series results."""
    raise NotImplementedError("M1 — docs/06_PARITY_TESTS.md section 2")


def run_parity(
    pine_csv: str | Path, config: AzimuthConfig, tol: float = 1e-6
) -> list[ParityResult]:
    """Recompute the core from the fixture's OHLCV and compare against Pine."""
    raise NotImplementedError("M1 — docs/06_PARITY_TESTS.md")
