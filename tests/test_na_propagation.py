"""Regression: na propagates. Never fill with 0.

``docs/06_PARITY_TESTS.md`` section 3, last row: "na handling -- Propagates. Use
np.nan, never 0 fill."

A zero fill is the worst available failure mode because 0 is a legal value for
every score in this system. ``ribScore = 0`` means a tangled ribbon; ``bbScore =
0`` means price at the basis. A warm-up region silently filled with zeros is
indistinguishable from a genuine neutral reading, and it drags the composite
toward the middle of the dead band for the first few hundred bars of every
backtest -- suppressing entries in a way no test of the signal itself would show.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.core import primitives as p

SRC = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
HIGH = SRC + 1.0
LOW = SRC - 1.0

WARMUP_CASES = {
    "sma": (lambda: p.sma(SRC, 4), 3),
    "ema": (lambda: p.ema(SRC, 4), 3),
    "rma": (lambda: p.rma(SRC, 4), 3),
    "stdev": (lambda: p.stdev(SRC, 4), 3),
    "rsi": (lambda: p.rsi(SRC, 4), 4),
    "percentrank": (lambda: p.percentrank(SRC, 4), 4),
    "correlation": (lambda: p.correlation(SRC, HIGH, 4), 3),
    "rolling_sum": (lambda: p.rolling_sum(SRC, 4), 3),
    "atr": (lambda: p.atr(HIGH, LOW, SRC, 4), 3),
    "change": (lambda: p.change(SRC), 1),
}


@pytest.mark.parametrize("name", sorted(WARMUP_CASES))
def test_warmup_region_is_nan_never_zero(name: str):
    fn, n_warmup = WARMUP_CASES[name]
    result = fn()

    head = result.iloc[:n_warmup]
    assert head.isna().all(), f"{name}: warm-up must be na, got {head.tolist()}"
    assert not (head == 0.0).any(), f"{name}: warm-up was zero-filled"


@pytest.mark.parametrize("name", sorted(WARMUP_CASES))
def test_a_value_appears_immediately_after_warmup(name: str):
    """The mirror of the above: na must not extend further than Pine's, or the
    burn-in of docs/06 section 2 trims the wrong bars."""
    fn, n_warmup = WARMUP_CASES[name]
    assert pd.notna(fn().iloc[n_warmup]), f"{name}: still na at bar {n_warmup}"


def test_series_too_short_returns_all_nan_not_zeros():
    short = pd.Series([1.0, 2.0])
    assert p.ema(short, 10).isna().all()
    assert p.rma(short, 10).isna().all()
    assert p.percentrank(short, 10).isna().all()


def test_pivot_series_is_nan_between_confirmations():
    """Pivot output is sparse by construction. Zero-filling it would invent
    divergences at every bar."""
    src = pd.Series([1.0, 2.0, 9.0, 2.0, 1.0, 2.0, 3.0])
    result = p.pivot_high(src, 2, 2)
    assert result.isna().sum() == len(result) - 1
    assert not (result.fillna(-1) == 0.0).any()


def test_rsi_flat_series_is_nan_not_fifty():
    """0/0 in the RS ratio. Pine yields na; several libraries return 50, which
    would read as a genuine neutral momentum signal on illiquid bars."""
    flat = pd.Series([100.0] * 30)
    assert p.rsi(flat, 14).iloc[-1] != pytest.approx(50.0)
    assert pd.isna(p.rsi(flat, 14).iloc[-1])


def test_rsi_all_gains_is_one_hundred_not_nan():
    """The other side of the same division: rs = inf, so rsi = 100 exactly."""
    rising = pd.Series(np.arange(1.0, 31.0))
    assert p.rsi(rising, 14).iloc[-1] == pytest.approx(100.0)


def test_boolean_primitives_are_false_during_warmup_not_na():
    """Pine comparisons against na are false, so crossover cannot fire in the
    warm-up. This is the ONE place a non-na default is correct -- and it is a
    bool, not a 0.0 masquerading as a score."""
    fast = p.sma(SRC, 3)
    assert p.crossover(SRC, fast).dtype == bool
    assert not p.crossover(SRC, fast).iloc[:2].any()
