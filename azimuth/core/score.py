"""Composite score. Implements ``docs/02_SPEC_SCORING.md`` section 1.

::

    score = 100 * sum(w_i * s_i) / sum(w_i)        in [-100, +100]

Weights are HYPERPARAMETERS and must be swept, not tuned by eye. An equal-weight
configuration (1,1,1,1,1) is a mandatory baseline in every walk-forward: if the
tuned weights do not beat equal weights out of sample, use equal weights. docs/02
section 1 notes they usually do not.

Ribbon, HTF and correlation are NOT regime-flipped -- they are directional context
in both regimes. Only Bollinger and RSI flip (docs/02 section 2).
"""

from __future__ import annotations

from itertools import combinations

import pandas as pd

from azimuth.config.schema import WeightsConfig
from azimuth.core._types import FloatSeries
from azimuth.core.primitives import EPS

__all__ = ["COMPONENT_NAMES", "component_correlation_matrix", "composite"]

COMPONENT_NAMES = ("ribbon", "bollinger", "rsi", "htf", "corr")


def composite(
    ribbon: FloatSeries,
    bollinger: FloatSeries,
    rsi: FloatSeries,
    htf: FloatSeries,
    corr: FloatSeries,
    weights: WeightsConfig,
) -> FloatSeries:
    """Weighted composite in [-100, +100]. Denominator guarded at ``EPS``.

    Mirrors ``pine/AZIMUTH.pine:194-196``, including the guard
    ``math.max(wRib + wBB + wRSI + wHTF + wCorr, 1e-10)``.

    NaN in any component propagates, so the composite is NaN through the longest
    warm-up -- 233 bars for the default ribbon. That is intended: the alternative
    is scoring on a partial component set, and 0 is a legal score meaning
    "neutral", so a zero-filled warm-up would be indistinguishable from a genuine
    neutral reading (see ``tests/test_na_propagation.py``).
    """
    weight_sum = max(
        weights.ribbon + weights.bollinger + weights.rsi + weights.htf + weights.corr, EPS
    )
    weighted = (
        weights.ribbon * ribbon
        + weights.bollinger * bollinger
        + weights.rsi * rsi
        + weights.htf * htf
        + weights.corr * corr
    )
    return 100.0 * weighted / weight_sum


def component_correlation_matrix(
    ribbon: FloatSeries,
    bollinger: FloatSeries,
    rsi: FloatSeries,
    htf: FloatSeries,
    corr: FloatSeries,
) -> dict[tuple[str, str], float]:
    """Pairwise correlations between the five component scores.

    docs/11_FINDINGS.md finding 16, M1 diagnostic. Ribbon, Bollinger and RSI are
    all momentum/location measures on the same close series over comparable
    horizons, so the ablation outcome in docs/02 section 5 may be predictable
    before any backtest runs.

    PRE-COMMITTED READING: if ``rho(ribbon, bollinger)`` and ``rho(ribbon, rsi)``
    both exceed **0.6**, state in the pre-registration -- as a prediction, before
    the sweep -- that any two of {ribbon, bollinger, rsi} can be zeroed at no
    out-of-sample cost. A pre-registered prediction that comes true is far
    stronger evidence than the same observation made post hoc, and it costs
    nothing to make now.

    Descriptive statistic of the signal, not a performance metric -- permitted
    before the parity gate lifts (CLAUDE.md rule 2).
    """
    series = {
        "ribbon": ribbon,
        "bollinger": bollinger,
        "rsi": rsi,
        "htf": htf,
        "corr": corr,
    }
    frame = pd.DataFrame(series).dropna()
    if frame.empty:
        raise ValueError(
            "no bars with all five components present -- the sample is shorter than "
            "the longest warm-up (233 bars for the default ribbon)"
        )

    return {(a, b): float(frame[a].corr(frame[b])) for a, b in combinations(COMPONENT_NAMES, 2)}
