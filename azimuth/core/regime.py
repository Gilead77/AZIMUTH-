"""Regime gate. Implements ``docs/01_SPEC_COMPONENTS.md`` section 6.

Two independent estimators, OR-combined::

    ER  = |close - close[n]| / sum(|close - close[1]|)  over n=20   -> ER > 0.30
    [+DI, -DI, ADX] = DMI(14, 14)                                   -> ADX > 20
    trending = (ER > 0.30) OR (ADX > 20)

``regime.mode`` forces trend-only or range-only. docs/01 section 6 is explicit that
the harness runs all three modes as SEPARATE HYPOTHESES and does not pick the best.

docs/11_FINDINGS.md finding 1 -- the most consequential open question in the
design. This boolean inverts the sign of both ``bbScore`` and ``rsiScore``. With
default weights a single flip moves the composite by up to

    2 * (0.8 + 0.8) / 4.3 * 100  ~=  74 points

with no price movement at all, which exceeds ``signal.enter = 45``. docs/02
section 3 applies a hysteresis dead band to the score for exactly this reason but
leaves the gate that inverts the score unprotected.

:func:`regime_diagnostics` measures it. It is a descriptive statistic of the
signal, not a performance metric, so it may be computed before the parity gate
lifts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from azimuth.config.schema import RegimeMode
from azimuth.core._types import BoolSeries, FloatSeries
from azimuth.core.primitives import EPS, dmi, rolling_sum

__all__ = ["adx", "efficiency_ratio", "regime_diagnostics", "trending"]


def efficiency_ratio(close: FloatSeries, length: int) -> FloatSeries:
    """Kaufman efficiency ratio: directional travel / total travel. Pine ``x_er``.

    ``|close - close[n]| / sum(|close - close[1]|)``, in [0, 1]. A straight line
    gives 1; a random walk gives roughly ``1/sqrt(n)``. Denominator guarded at
    ``EPS`` per ``pine/AZIMUTH.pine:182``.
    """
    if length < 1:
        raise ValueError(f"er_length must be >= 1, got {length}")

    directional = (close - close.shift(length)).abs()
    total = rolling_sum((close - close.shift(1)).abs(), length)
    return directional / total.clip(lower=EPS)


def adx(high: FloatSeries, low: FloatSeries, close: FloatSeries, length: int) -> FloatSeries:
    """ADX alone, Pine's ``x_adx``. ``ta.dmi(adxLen, adxLen)`` -- both arguments
    are ``adxLen`` at ``pine/AZIMUTH.pine:183``, so the DI length and the ADX
    smoothing are the same parameter."""
    _, _, adx_values = dmi(high, low, close, length, length)
    return adx_values


def trending(
    high: FloatSeries,
    low: FloatSeries,
    close: FloatSeries,
    er_length: int,
    er_threshold: float,
    adx_length: int,
    adx_threshold: float,
    mode: RegimeMode = "adaptive",
) -> BoolSeries:
    """The regime boolean. OR of the ER and ADX conditions, or forced by ``mode``.

    NaN comparisons are False in Pine, so the warm-up reads as "range". That is
    reproduced rather than masked: during warm-up the composite is NaN anyway and
    no signal can fire, but forcing "trend" there would change which branch the
    first real bars take.
    """
    if mode == "trend_only":
        return pd.Series(True, index=close.index)
    if mode == "range_only":
        return pd.Series(False, index=close.index)

    er = efficiency_ratio(close, er_length) > er_threshold
    adx_hot = adx(high, low, close, adx_length) > adx_threshold
    return (er | adx_hot).fillna(value=False).astype(bool)


def regime_diagnostics(trending_flags: BoolSeries) -> dict[str, float]:
    """Duty cycle and flip statistics for the regime gate.

    docs/11_FINDINGS.md finding 1, M1 diagnostic. Returns:

    * ``duty_cycle`` -- fraction of bars in the trend branch;
    * ``n_flips`` and ``flips_per_1000_bars``;
    * ``mean_trend_run`` / ``mean_range_run`` -- average consecutive bars per state.

    PRE-COMMITTED READING, so it cannot be reinterpreted after the numbers are in:
    if the range branch occupies **less than 20%** of bars, OR the mean run length
    of either state is **under 5 bars**, the polarity switch is acting as noise
    amplification rather than adaptation, and that goes into the pre-registration
    as a stated expectation before any sweep runs.

    Rationale for the thresholds: the mean-reversion branch fitted on under a fifth
    of the sample is fitted on an unrepresentative subsample, and a state that
    survives fewer than 5 bars cannot describe a market regime -- it is describing
    ADX crossing 20.

    This is a descriptive statistic of the signal, NOT a performance metric --
    permitted before the parity gate lifts (CLAUDE.md rule 2).
    """
    flags = trending_flags.to_numpy(dtype=bool)
    n = flags.size
    if n == 0:
        raise ValueError("cannot diagnose an empty regime series")

    flips = int(np.count_nonzero(flags[1:] != flags[:-1]))
    n_trend = int(np.count_nonzero(flags))

    # Run lengths: a flip starts a new run, so runs = flips + 1.
    boundaries = np.flatnonzero(np.diff(flags.astype(int))) + 1
    runs = np.diff(np.concatenate(([0], boundaries, [n])))
    run_is_trend = flags[np.concatenate(([0], boundaries))]

    trend_runs = runs[run_is_trend]
    range_runs = runs[~run_is_trend]

    return {
        "n_bars": float(n),
        "duty_cycle": n_trend / n,
        "range_share": 1.0 - n_trend / n,
        "n_flips": float(flips),
        "flips_per_1000_bars": 1000.0 * flips / n,
        "mean_trend_run": float(trend_runs.mean()) if trend_runs.size else 0.0,
        "mean_range_run": float(range_runs.mean()) if range_runs.size else 0.0,
    }
