"""Regression: ``ta.stdev`` is POPULATION (ddof=0); pandas defaults to ddof=1.

``docs/06_PARITY_TESTS.md`` section 3 and CLAUDE.md's known traps. On the
20-period Bollinger basis the discrepancy is a factor of sqrt(20/19) ~= 1.026 on
the band width: small enough to look entirely plausible on a chart, large enough
to fail the 1e-6 parity gate on every single bar.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from azimuth.core.primitives import stdev

# Textbook fixture: mean 5, squared deviations sum to 32 over 8 observations.
SRC = pd.Series([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])

POPULATION = 2.0  # sqrt(32/8)
SAMPLE = math.sqrt(32.0 / 7.0)  # ~2.13809, what pandas gives by default


def test_stdev_is_population():
    assert stdev(SRC, 8).iloc[7] == pytest.approx(POPULATION, abs=1e-12)


def test_pandas_default_is_the_sample_standard_deviation():
    """Confirms the trap is real and still present in this pandas version."""
    assert SRC.rolling(8).std().iloc[7] == pytest.approx(SAMPLE, abs=1e-12)
    assert abs(SAMPLE - POPULATION) > 0.1, "the two conventions must be distinguishable"


def test_the_difference_would_break_the_parity_gate():
    ours = stdev(SRC, 8).iloc[7]
    naive = SRC.rolling(8).std().iloc[7]
    assert abs(ours - naive) > 1e-6, "difference must exceed the docs/06 tolerance"


def test_ratio_is_the_bessel_correction():
    """Pins the exact relationship, so a future 'fix' that scales by the wrong
    factor is caught rather than merely nudged."""
    rng = np.random.default_rng(11)
    src = pd.Series(rng.normal(0, 1, 200))
    length = 20

    ours = stdev(src, length)
    naive = src.rolling(length).std()
    ratio = (naive / ours).dropna()

    np.testing.assert_allclose(ratio, math.sqrt(length / (length - 1)), rtol=1e-12)
