"""Cross-asset correlation. Implements ``docs/01_SPEC_COMPONENTS.md`` section 5.

Correlation is computed on LOG RETURNS, never prices: price-level correlation
between two trending series is close to meaningless (spurious regression)::

    r_own   = ln(close / close[1])
    r_ref   = ln(ref / ref[1])
    rho_j   = correlation(r_own, r_ref, 60)
    trend_j = sign(ref - EMA(ref, 50))
    contrib_j = |rho_j| >= rho_min ? rho_j * trend_j : 0
    corrScore = clip(sum(contrib_j) / count(active j))

Negative rho flips the vote, which is correct for DXY against most risk assets.

TWO CAVEATS, both in docs/11_FINDINGS.md:

finding 3 -- a reference on a different trading calendar (DXY 24/5, SPX ~6.5h/day)
forward-fills across bars it did not trade, injecting structural zero returns. On
a 1H BTC chart against SPX, roughly 73% of bars carry ``r_ref = 0`` and the 60-bar
rho rests on ~16 real observations. Pine and pandas forward-fill identically, so
``azimuth parity`` PASSES on a number that carries almost no information.
:func:`effective_observations` measures it.

finding 16 -- ``rho`` measures CONTEMPORANEOUS return correlation, but the
component uses it to weight a claim about the reference's trend predicting our
next-bar return. Correlation is not lead-lag. This is the component most likely to
fail the ablation in docs/02 section 5.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from azimuth.core._types import FloatSeries
from azimuth.core.primitives import EPS, correlation, ema
from azimuth.core.ribbon import clip

__all__ = [
    "correlation_score",
    "crowding",
    "effective_observations",
    "log_returns",
    "reference_contribution",
    "rho_stability",
]


def log_returns(close: FloatSeries) -> FloatSeries:
    """``ln(close / close[1])``. Denominator guarded at ``EPS``, matching Pine.

    ``pine/AZIMUTH.pine:159`` is ``math.log(close / math.max(close[1], 1e-10))``.
    """
    ratio = close / close.shift(1).clip(lower=EPS)
    return pd.Series(np.log(ratio.to_numpy(dtype=float)), index=close.index, dtype=float)


def _pine_sign(x: FloatSeries) -> FloatSeries:
    """``math.sign``: -1, 0 or +1, with 0 preserved.

    Unlike the HTF votes (which Pine writes as ternaries), the correlation trend
    term at ``pine/AZIMUTH.pine:165`` really is ``math.sign``, so an exactly-flat
    reference contributes nothing rather than voting short.
    """
    return pd.Series(np.sign(x.to_numpy(dtype=float)), index=x.index, dtype=float)


def reference_contribution(
    own_returns: FloatSeries,
    ref_close: FloatSeries,
    length: int,
    min_abs_rho: float,
    ref_ema: int,
) -> tuple[FloatSeries, FloatSeries, FloatSeries]:
    """Return ``(rho, contribution, active)`` for one reference.

    ``active`` is 1.0 where ``|rho| >= min_abs_rho`` and 0.0 elsewhere; it is the
    denominator of the aggregate, so an inactive reference does not dilute the
    vote of an active one.
    """
    ref_returns = log_returns(ref_close)
    rho = correlation(own_returns, ref_returns, length)
    trend = _pine_sign(ref_close - ema(ref_close, ref_ema))

    gate = rho.abs() >= min_abs_rho
    active = (gate & rho.notna()).astype(float)
    contribution = (rho * trend).where(gate & rho.notna(), 0.0)

    return rho, contribution, active


def correlation_score(
    close: FloatSeries,
    refs: Sequence[FloatSeries],
    length: int,
    min_abs_rho: float,
    ref_ema: int,
) -> FloatSeries:
    """Aggregate contribution over active references. Pine's ``x_corr``.

    Zero when no reference clears the ``|rho|`` floor -- ``pine/AZIMUTH.pine:175``
    is ``corrN > 0 ? clip(...) : 0.0``, so the component abstains rather than
    going na and poisoning the composite.
    """
    if not refs:
        return pd.Series(0.0, index=close.index, dtype=float)

    own = log_returns(close)
    total = pd.Series(0.0, index=close.index, dtype=float)
    count = pd.Series(0.0, index=close.index, dtype=float)

    for ref in refs:
        _, contribution, active = reference_contribution(
            own, ref.reindex(close.index), length, min_abs_rho, ref_ema
        )
        total = total + contribution
        count = count + active

    scored = clip(total / count.where(count > 0.0))
    return scored.fillna(0.0)


def crowding(refs_rho: Sequence[FloatSeries], n_enabled: int | None = None) -> FloatSeries:
    """``mean(|rho_j|)`` -- a RISK measure, not a directional one.

    High crowding means everything is one trade. Feeds position sizing, never the
    directional score (docs/01 section 5).

    docs/11_FINDINGS.md finding 0: the Pine implementation had an operator
    precedence bug here that pinned the denominator at 1, letting crowding exceed
    its documented [0, 1] range. Fixed in commit 1; this divides by the count of
    ENABLED references, matching the corrected Pine. Note that is *enabled*, not
    *active* -- a reference below the ``|rho|`` floor still contributes its small
    ``|rho|`` to the crowding average, which is correct: crowding measures how
    much everything is moving together, not how many references are voting.
    """
    if not refs_rho:
        raise ValueError("crowding needs at least one reference series")

    denominator = max(n_enabled if n_enabled is not None else len(refs_rho), 1)
    total = pd.Series(0.0, index=refs_rho[0].index, dtype=float)
    for rho in refs_rho:
        total = total + rho.abs().fillna(0.0)  # Pine: nz(rho)
    return total / denominator


def effective_observations(close: FloatSeries, ref_close: FloatSeries, length: int) -> FloatSeries:
    """Fraction of the correlation window backed by a real reference move.

    docs/11_FINDINGS.md finding 3, M1 diagnostic. A reference on a different
    trading calendar is forward-filled across bars it did not trade, so its log
    return is a structural zero there. This reports, per bar, what share of the
    ``length``-bar window carried a non-zero reference return.

    A value of 0.27 means the 60-bar rho rests on about 16 real observations. The
    number is still computed, still matches Pine to 1e-15, and still passes the
    ``|rho| >= corr.min_abs_rho`` gate -- which is exactly why this needs
    measuring rather than assuming.

    Descriptive statistic of the inputs, not a performance metric: permitted
    before the parity gate lifts (CLAUDE.md rule 2).
    """
    moved = (log_returns(ref_close.reindex(close.index)) != 0.0).astype(float)
    return moved.rolling(length).mean()


def rho_stability(own: FloatSeries, ref: FloatSeries, length: int) -> tuple[float, float]:
    """Rho over each half of the sample, for ``--check-rho-stability``.

    docs/07 section 5: if the sign flips between halves, DROP that reference.
    Unstable correlations actively degrade the score -- they cast confident votes
    in the wrong direction.

    Returns:
        ``(rho_first_half, rho_second_half)``, each the mean rolling correlation
        over that half. NaN where a half is too short for the window.
    """
    own_returns = log_returns(own)
    ref_returns = log_returns(ref.reindex(own.index))
    rho = correlation(own_returns, ref_returns, length)

    midpoint = len(rho) // 2
    return float(rho.iloc[:midpoint].mean()), float(rho.iloc[midpoint:].mean())
