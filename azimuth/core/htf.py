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

Construction, per docs/04 section 6::

    htf = df.resample(rule, label="right", closed="right").agg(OHLCV_AGG)
    htf_score = compute_htf_score(htf).shift(1)
    aligned = htf_score.reindex(df.index, method="ffill")
"""

from __future__ import annotations

import pandas as pd

from azimuth.core._types import FloatSeries


def htf_bias(htf_close: FloatSeries, ema_length: int, rsi_length: int = 14) -> FloatSeries:
    """Three-way sign vote in the HTF context, in {-1, -1/3, +1/3, +1}.

    Returns the UNSHIFTED series. Shifting is the caller's job in
    :func:`align_to_base`, so that the confirmation step is explicit and testable
    rather than buried.
    """
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 4")


def align_to_base(
    htf_score: FloatSeries, base_index: pd.DatetimeIndex, confirmed_only: bool = True
) -> FloatSeries:
    """Shift by one HTF bar, then forward-fill onto the base timeframe index.

    Args:
        confirmed_only: Must be True. Present only so the lookahead variant can be
            constructed inside ``tests/test_htf_alignment.py`` to prove the shift
            matters. Production callers get True from the schema, which rejects
            False outright.
    """
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 6")


def htf_score(
    base_index: pd.DatetimeIndex,
    htf1: FloatSeries,
    htf2: FloatSeries | None,
    weight_tf1: float = 0.6,
) -> FloatSeries:
    """Weighted blend, exported to Pine's ``x_htf``.

    docs/11_FINDINGS.md finding 11: docs/06 section 2 sets this tolerance to
    "exact", but 0.6*(1/3) is not representable in binary64, so strict equality
    fails on correct code. Compare at 1e-9 plus a distinct-value-set assertion.
    """
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 4")
