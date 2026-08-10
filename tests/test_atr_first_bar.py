"""Regression: true range on the first bar, where ``close[1]`` does not exist.

``ta.atr`` uses ``ta.tr(true)``, which falls back to ``high - low``. The bare
``ta.tr`` used inside ``ta.dmi`` returns na instead. The difference moves the RMA
seed by one bar; it is invisible after the 283-bar burn-in of ``docs/06``
section 2, and it is free to get right.

Filing this separately because ``pine/AZIMUTH.pine:123`` divides the ribbon slope
by ATR, so an ATR seeding error surfaces as a ``x_ribbon`` parity failure and
sends the reader hunting through the EMA code instead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.core.primitives import atr, rma, true_range

HIGH = pd.Series([10.0, 12.0, 13.0, 12.0, 14.0])
LOW = pd.Series([8.0, 9.0, 11.0, 10.0, 11.0])
CLOSE = pd.Series([9.0, 11.0, 12.0, 10.5, 13.0])

# bar 0: no previous close
# bar 1: max(12-9,  |12-9|,    |9-9|)      = 3
# bar 2: max(13-11, |13-11|,   |11-11|)    = 2
# bar 3: max(12-10, |12-12|,   |10-12|)    = 2
# bar 4: max(14-11, |14-10.5|, |11-10.5|)  = 3.5
TR_TAIL = [3.0, 2.0, 2.0, 3.5]


def test_handle_na_true_falls_back_to_high_minus_low():
    tr = true_range(HIGH, LOW, CLOSE, handle_na=True)
    assert tr.iloc[0] == pytest.approx(2.0), "high - low on the first bar"
    np.testing.assert_allclose(tr.iloc[1:], TR_TAIL, rtol=0, atol=1e-12)


def test_handle_na_false_leaves_the_first_bar_na():
    tr = true_range(HIGH, LOW, CLOSE, handle_na=False)
    assert pd.isna(tr.iloc[0])
    np.testing.assert_allclose(tr.iloc[1:], TR_TAIL, rtol=0, atol=1e-12)


def test_atr_uses_the_handle_na_true_variant():
    """ta.atr == rma(ta.tr(true), length): the seed therefore includes bar 0."""
    expected = rma(true_range(HIGH, LOW, CLOSE, handle_na=True), 3)
    pd.testing.assert_series_equal(atr(HIGH, LOW, CLOSE, 3), expected, check_names=False)


def test_atr_seed_is_one_bar_earlier_than_the_dmi_variant():
    ours = atr(HIGH, LOW, CLOSE, 3)
    dmi_style = rma(true_range(HIGH, LOW, CLOSE, handle_na=False), 3)

    first_ours = int(np.flatnonzero(ours.notna())[0])
    first_dmi = int(np.flatnonzero(dmi_style.notna())[0])
    assert first_dmi == first_ours + 1


def test_true_range_covers_gaps_not_just_the_bar_range():
    """A gap down: |low - close[1]| dominates, and high-low alone understates it."""
    high = pd.Series([100.0, 90.0])
    low = pd.Series([98.0, 88.0])
    close = pd.Series([99.0, 89.0])

    tr = true_range(high, low, close, handle_na=True)
    assert tr.iloc[1] == pytest.approx(11.0), "|88 - 99| beats the 2.0 bar range"
