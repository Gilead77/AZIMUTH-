"""Benchmark nulls. Implements ``docs/05_SPEC_VALIDATION.md`` sections 4.2-4.3.

RANDOM-ENTRY (4.2). Random long/short entries matched to AZIMUTH on trade count,
holding-period distribution and long/short ratio, using the SAME stops and targets.
This isolates signal quality from exit logic. docs/05 is blunt about why it
matters: it is common for a "system" to owe its entire result to a 2R target with
an ATR stop, with the signal contributing nothing.

BUY & HOLD (4.3). Both raw and volatility-matched -- lever B&H to AZIMUTH's
realised vol. Beating B&H on absolute return while running 3x the volatility is not
an edge.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def random_entry_benchmark(
    df: pd.DataFrame,
    n_trades: int,
    holding_periods: pd.Series[int],
    long_ratio: float,
    n_samples: int,
    rng: np.random.Generator,
) -> pd.Series[float]:
    """Matched random-entry Sharpe distribution (section 4.2)."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 4.2")


def buy_and_hold(
    df: pd.DataFrame, vol_match_to: pd.Series[float] | None = None
) -> pd.Series[float]:
    """Buy & hold equity, raw or levered to a target realised vol (section 4.3)."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 4.3")
