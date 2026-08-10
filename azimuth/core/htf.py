"""Higher-timeframe bias. Implements ``docs/01_SPEC_COMPONENTS.md`` section 4.

Computed IN the HTF context, then pulled down::

    he = EMA(close, 50)                                   # in HTF
    hr = RSI(close, 14)                                   # in HTF
    s  = (sign(close - he) + sign(he - he[3]) + sign(hr - 50)) / 3
    value = s[1]                                          # previous CLOSED HTF bar

    htfScore = clip(0.6 * HTF1 + 0.4 * HTF2)

REPAINT CONTRACT (docs/01 section 4, docs/03 section 2, docs/04 section 6).
The ``.shift(1)`` is the Python equivalent of returning ``s[1]`` from inside
``request.security(..., lookahead = barmerge.lookahead_off)``. It fixes the value
from the moment the HTF bar closes, at a cost of up to one HTF bar of lag.

That cost is non-negotiable. Omitting the shift is the single most likely source
of a fake edge in this entire project (docs/04 section 6). ``htf.confirmed_only``
is pinned true by a schema validator and is never swept.

See also docs/11_FINDINGS.md finding 21: the resample must use ``closed="left"``,
not the ``closed="right"`` in docs/04 section 6, or every HTF bar aggregates the
wrong base bars. The grouping and the shift are independent -- fixing a grouping
error by adjusting the shift converts it into a lookahead error.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from azimuth.core._types import FloatSeries
from azimuth.core.primitives import ema, rsi
from azimuth.core.ribbon import clip

__all__ = ["align_to_base", "htf_bias", "htf_component", "htf_score"]

RSI_CENTRE = 50.0


def _pine_sign(x: FloatSeries) -> FloatSeries:
    """Pine's ``cond ? 1 : -1``, which is NOT ``math.sign``.

    ``docs/01`` section 4 writes the three votes as ``sign(...)``, but
    ``pine/AZIMUTH.pine:151`` implements them as ternaries::

        (close > he ? 1 : -1) + (he > he[3] ? 1 : -1) + (hr > 50 ? 1 : -1)

    The two differ on exact equality: ``math.sign(0)`` is 0, the ternary gives -1.
    Pine wins -- parity is against the code that runs, not the prose. In practice
    equality happens when price sits exactly on the EMA, which is rare on real
    data but common on synthetic test series, so the distinction shows up in tests
    long before it shows up in a fixture.

    NaN propagates rather than resolving to -1, so the warm-up stays NaN.
    """
    return pd.Series(
        np.where(x.isna(), np.nan, np.where(x > 0.0, 1.0, -1.0)),
        index=x.index,
        dtype=float,
    )


def htf_bias(
    htf_close: FloatSeries,
    ema_length: int,
    rsi_length: int = 14,
    slope_lookback: int = 3,
) -> FloatSeries:
    """Three-way sign vote in the HTF context, in {-1, -1/3, +1/3, +1}.

    Returns the UNSHIFTED series. Shifting is the caller's job in
    :func:`align_to_base`, so that the confirmation step is explicit and testable
    rather than buried.

    Args:
        rsi_length: FINDING-20 -- hardcoded to 14 at ``pine/AZIMUTH.pine:150``.
        slope_lookback: FINDING-20 -- the ``he[3]`` at ``pine/AZIMUTH.pine:151``.
    """
    he = ema(htf_close, ema_length)
    hr = rsi(htf_close, rsi_length)

    votes = (
        _pine_sign(htf_close - he)
        + _pine_sign(he - he.shift(slope_lookback))
        + _pine_sign(hr - RSI_CENTRE)
    )
    return votes / 3.0


def align_to_base(
    htf_series: FloatSeries, base_index: pd.DatetimeIndex, confirmed_only: bool = True
) -> FloatSeries:
    """Shift by one HTF bar, then forward-fill onto the base timeframe index.

    Args:
        confirmed_only: Must be True in production -- the schema rejects False
            outright (``docs/07`` section 1: "Never sweep. False = lookahead").
            The parameter exists only so ``tests/test_htf_alignment.py`` can
            construct the lookahead variant and prove the shift is what prevents
            it. A negative control, in the same spirit as the planted leaks in
            ``tests/test_lookahead.py``.

    The ``.shift(1)`` operates on the HTF index, so it is one HTF BAR, not one
    base bar. Combined with the right-labelling from
    :func:`azimuth.data.resample.resample_htf` -- where a bar carries the
    timestamp at which it closed -- a base bar at time ``t`` reads the last HTF
    bar to have closed strictly before the currently forming one, which is
    precisely what ``request.security(..., s[1], lookahead_off)`` returns.
    """
    confirmed = htf_series.shift(1) if confirmed_only else htf_series
    return confirmed.reindex(base_index, method="ffill")


def htf_score(
    htf1: FloatSeries,
    htf2: FloatSeries | None,
    weight_tf1: float = 0.6,
) -> FloatSeries:
    """Weighted blend, exported to Pine's ``x_htf``.

    ``clip(0.6*HTF1 + 0.4*HTF2)``, or ``nz(HTF1)`` when the second horizon is off
    or unavailable -- matching ``pine/AZIMUTH.pine:156``, which falls back to
    ``nz(h1)`` and therefore yields 0 rather than na during HTF1's warm-up.

    docs/11_FINDINGS.md finding 11: docs/06 section 2 sets this tolerance to
    "exact", but 0.6*(1/3) is not representable in binary64, so strict equality
    fails on correct code. Compare at 1e-9 plus a distinct-value-set assertion.
    """
    if htf2 is None:
        return clip(htf1.fillna(0.0))

    blended = htf1 * weight_tf1 + htf2 * (1.0 - weight_tf1)
    # Pine: `htfUse2 and not na(h2) ? (h1*0.6 + h2*0.4) : nz(h1)`
    return clip(blended.where(htf2.notna(), htf1.fillna(0.0)).fillna(0.0))


def htf_component(
    df: pd.DataFrame,
    tf1: str,
    tf2: str | None,
    ema_length: int,
    rsi_length: int = 14,
    slope_lookback: int = 3,
    weight_tf1: float = 0.6,
    confirmed_only: bool = True,
) -> FloatSeries:
    """End-to-end HTF bias on a base-timeframe frame: resample, bias, shift, align.

    The one function callers should use. Assembling the four steps by hand is how
    the shift gets dropped.
    """
    from azimuth.data.resample import resample_htf, timeframe_to_rule

    base_index = pd.DatetimeIndex(df.index)

    def one(timeframe: str) -> FloatSeries:
        htf = resample_htf(df, timeframe_to_rule(timeframe))
        bias = htf_bias(htf["close"], ema_length, rsi_length, slope_lookback)
        return align_to_base(bias, base_index, confirmed_only=confirmed_only)

    return htf_score(one(tf1), one(tf2) if tf2 else None, weight_tf1)
