"""Regression: ``ta.dmi`` uses Wilder smoothing at every step.

``docs/06_PARITY_TESTS.md`` section 3: "Implement from scratch; ta.ADX in other
libs commonly differs." The usual divergence is an EMA or SMA substituted for one
of the three RMA steps, which shifts ADX by several points -- more than enough to
move it across the ``regime.adx_threshold`` of 20 and flip the regime gate, which
in turn inverts the sign of two components (docs/11_FINDINGS.md finding 1).

Fixture below is hand-computed at ``di_length = adx_smoothing = 2`` so every step
is a plain average and the arithmetic can be checked on paper.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.core.primitives import dmi

HIGH = pd.Series([10.0, 12.0, 13.0, 12.0, 14.0])
LOW = pd.Series([8.0, 9.0, 11.0, 10.0, 11.0])
CLOSE = pd.Series([9.0, 11.0, 12.0, 10.5, 13.0])

# up      = [na,  2,  1, -1,  2]      down    = [na, -1, -2,  1, -1]
# +DM     = [na,  2,  1,  0,  2]      -DM     = [na,  0,  0,  1,  0]
# TR      = [na,  3,  2,  2,  3.5]    (handle_na=False inside dmi)
# rma(TR) = [na, na, 2.5, 2.25, 2.875]
# +DI     = [na, na, 60,  33.333..., 47.826...]
# -DI     = [na, na,  0,  22.222...,  8.696...]
# ratio   = [na, na,  1.0, 0.2, 0.6923...]
# ADX     = [na, na, na,  60.0, 64.6153...]
EXPECTED_PLUS = [60.0, 100.0 * 0.75 / 2.25, 100.0 * 1.375 / 2.875]
EXPECTED_MINUS = [0.0, 100.0 * 0.5 / 2.25, 100.0 * 0.25 / 2.875]
EXPECTED_ADX = [60.0, 100.0 * 0.64615384615384615]


def test_dmi_matches_hand_computed_wilder_values():
    plus, minus, adx = dmi(HIGH, LOW, CLOSE, 2, 2)

    np.testing.assert_allclose(plus.iloc[2:], EXPECTED_PLUS, rtol=0, atol=1e-9)
    np.testing.assert_allclose(minus.iloc[2:], EXPECTED_MINUS, rtol=0, atol=1e-9)
    np.testing.assert_allclose(adx.iloc[3:], EXPECTED_ADX, rtol=0, atol=1e-9)


def test_dmi_returns_a_three_tuple():
    """docs/03 section 7 item 2: unpack all three."""
    result = dmi(HIGH, LOW, CLOSE, 2, 2)
    assert isinstance(result, tuple) and len(result) == 3


def test_adx_is_na_until_both_smoothers_have_seeded():
    plus, _minus, adx = dmi(HIGH, LOW, CLOSE, 2, 2)
    assert plus.iloc[:2].isna().all()
    assert adx.iloc[:3].isna().all(), "ADX seeds one step later than DI -- it smooths DI"


def test_ema_smoothing_gives_a_materially_different_adx():
    """The common third-party bug. Demonstrated at realistic lengths (14, 14)."""
    rng = np.random.default_rng(17)
    n = 400
    close = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, n)))
    high = close + np.abs(rng.normal(0, 0.8, n))
    low = close - np.abs(rng.normal(0, 0.8, n))

    _, _, ours = dmi(high, low, close, 14, 14)

    # Same construction, but with alpha = 2/(n+1) instead of Wilder's 1/n.
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=close.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=close.index)
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)

    e = {"span": 14, "adjust": False}
    trur = tr.ewm(**e).mean()
    plus = 100 * plus_dm.ewm(**e).mean() / trur
    minus = 100 * minus_dm.ewm(**e).mean() / trur
    total = (plus + minus).replace(0.0, 1.0)
    naive_adx = (100 * ((plus - minus).abs() / total).ewm(**e).mean()).iloc[300]

    gap = abs(ours.iloc[300] - naive_adx)
    assert gap > 1.0, (
        f"EMA-smoothed ADX differs from Wilder by only {gap:.4f} on this sample; "
        "the fixture no longer demonstrates the trap"
    )


def test_adx_stays_within_zero_and_one_hundred():
    rng = np.random.default_rng(23)
    n = 500
    close = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, n)))
    high = close + np.abs(rng.normal(0, 0.8, n))
    low = close - np.abs(rng.normal(0, 0.8, n))

    plus, minus, adx = dmi(high, low, close, 14, 14)
    for name, series in (("+DI", plus), ("-DI", minus), ("ADX", adx)):
        values = series.dropna()
        assert values.min() >= -1e-9 and values.max() <= 100.0 + 1e-9, f"{name} out of range"


def test_zero_directional_movement_uses_the_sum_guard():
    """The ``sum == 0 ? 1 : sum`` branch of the reference implementation.

    Constructed so true range is strictly positive while both DM series are zero:
    high and low never move, so ``up = down = 0`` and neither DM can fire, but
    close oscillates inside the range so TR stays at the 20-point bar width.
    +DI and -DI are then both 0, their sum is 0, and without the guard the ratio
    would be 0/0 and NaN would poison every subsequent bar through the RMA.
    """
    n = 40
    high = pd.Series([110.0] * n)
    low = pd.Series([90.0] * n)
    close = pd.Series([100.0 + (5.0 if i % 2 else -5.0) for i in range(n)])

    plus, minus, adx = dmi(high, low, close, 14, 14)

    assert plus.iloc[-1] == pytest.approx(0.0)
    assert minus.iloc[-1] == pytest.approx(0.0)
    assert adx.iloc[-1] == pytest.approx(0.0), "guard must yield 0, never NaN"

    # Once seeded, ADX must never lapse back to NaN -- that is what a 0/0 ratio
    # entering the RMA would do. (It seeds at 27: bar 14 for the DI smoother, 14
    # more for the ADX smoother on top.)
    first_value = int(np.flatnonzero(adx.notna())[0])
    assert adx.iloc[first_value:].notna().all(), (
        "a NaN reappeared after seeding -- the sum==0 guard leaked into the RMA"
    )


def test_perfectly_flat_series_is_na_matching_pine():
    """Degenerate input: high == low == close, so true range is 0 and ``trur``
    is 0. Pine's ``100 * rma(+DM) / trur`` is then 0/0 = na, and ``fixnan`` has no
    earlier value to carry, so na is the correct answer rather than 0.

    Recorded because the tempting 'fix' is to clamp the denominator, which would
    silently report ADX = 0 -- a genuine 'no trend' reading -- for data that
    actually says nothing at all.
    """
    flat = pd.Series([100.0] * 40)
    plus, _minus, adx = dmi(flat, flat, flat, 14, 14)

    assert pd.isna(plus.iloc[-1])
    assert pd.isna(adx.iloc[-1])


def test_output_has_no_interior_na_gaps():
    """Once each series has seeded it must stay defined for the rest of the sample.

    A single interior na would propagate through the remaining RMA steps and
    silently blank the regime gate from that bar onward -- which, per
    docs/11_FINDINGS.md finding 1, inverts the sign of two components rather than
    merely muting them.
    """
    rng = np.random.default_rng(31)
    n = 400
    close = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, n)))
    high = close + np.abs(rng.normal(0, 0.6, n))
    low = close - np.abs(rng.normal(0, 0.6, n))

    for name, series in zip(("+DI", "-DI", "ADX"), dmi(high, low, close, 14, 14), strict=True):
        valid = np.flatnonzero(series.notna())
        assert valid.size, f"{name} never produced a value"
        assert series.iloc[valid[0] :].notna().all(), f"{name} has an interior na gap"
