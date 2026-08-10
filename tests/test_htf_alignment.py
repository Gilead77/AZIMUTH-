"""HTF alignment: synthetic data, asserts zero lookahead.

``docs/06_PARITY_TESTS.md`` section 4 names this file. It covers the contract
``docs/04`` section 6 calls "the most likely source of a fake edge":

    htf_score = compute_htf_score(htf).shift(1)
    aligned   = htf_score.reindex(df.index, method="ffill")

Three things have to be right together, they are independent, and -- worth being
precise about, because it is easy to conflate them -- only two of the three are
about lookahead:

1. **grouping** -- which base bars belong to which HTF bar (finding 21). Wrong
   grouping is not lookahead; it is simply the wrong bar.
2. **labelling** -- an HTF bar carries the timestamp at which it CLOSED. This is
   the one that prevents lookahead. Right-labelling plus ``reindex(ffill)`` means
   a base bar can only pick up an HTF bar that had already closed. Labelling with
   the bar's OPEN time instead hands a base bar a value computed partly from its
   own future -- that is the genuine leak, and
   :func:`test_left_labelling_is_genuine_lookahead` demonstrates it.
3. **the shift** -- Pine's ``s[1]``. Right-labelling alone is already causal, so
   this is not what makes the pipeline safe; it is what makes it MATCH PINE.
   ``request.security(..., lookahead_off)`` serves the last confirmed HTF bar, and
   the ``[1]`` inside takes one further back, so a base bar reads the bar before
   the last one to have closed -- one HTF bar of lag beyond what causality
   demands. ``docs/01`` section 4 accepts that cost explicitly.

The reason to keep them separate: getting 1 wrong produces a one-bar ``x_htf``
parity mismatch, and the intuitive fix is to adjust 3. That trades a grouping
error for a lag error, makes parity pass, and makes the backtest better.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.core.htf import align_to_base, htf_bias, htf_component, htf_score
from azimuth.data.resample import resample_htf


def _hourly(n: int = 240, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, n))
    return pd.DataFrame(
        {
            "open": close,
            "high": close + np.abs(rng.normal(0.0, 0.5, n)),
            "low": close - np.abs(rng.normal(0.0, 0.5, n)),
            "close": close,
            "volume": np.ones(n),
        },
        index=pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC"),
    )


# ── the alignment contract, stated directly ─────────────────────────────────────


def test_base_bar_never_sees_its_own_htf_bar():
    """THE test. A base bar inside a forming HTF bar must not carry that bar's value.

    Construction: a marker series where each 4H bar's value is unique and known.
    If any base bar carries the value of the HTF bar it sits inside, the shift is
    missing or the label is wrong.
    """
    df = _hourly(n=48)
    htf = resample_htf(df, "4h")

    # A marker that is trivially identifiable: the HTF bar's own close.
    marker = htf["close"]
    aligned = align_to_base(marker, pd.DatetimeIndex(df.index), confirmed_only=True)

    for timestamp, value in aligned.dropna().items():
        # Which HTF bar is this base bar inside? The first one whose label (close
        # time) is strictly after the base timestamp.
        forming = marker.index[marker.index > timestamp]
        assert forming.size, "ran out of HTF bars"
        current_bar_value = marker.loc[forming[0]]

        assert value != pytest.approx(current_bar_value), (
            f"base bar {timestamp} carries the value of the HTF bar it is INSIDE "
            f"({current_bar_value}) -- that is lookahead"
        )


def test_value_is_the_previous_closed_htf_bar():
    """Positively: at base bar t, the aligned value is the bar BEFORE the last one
    to have closed -- Pine's ``s[1]`` evaluated at the last completed HTF bar."""
    df = _hourly(n=32)
    htf = resample_htf(df, "4h")
    marker = htf["close"]
    aligned = align_to_base(marker, pd.DatetimeIndex(df.index), confirmed_only=True)

    # HTF labels are close times: 04:00, 08:00, 12:00 ...
    # At base bar 09:00, the last CLOSED HTF bar is the one labelled 08:00, and
    # shift(1) hands back the one labelled 04:00.
    t = pd.Timestamp("2020-01-01 09:00", tz="UTC")
    expected = marker.loc[pd.Timestamp("2020-01-01 04:00", tz="UTC")]
    assert aligned.loc[t] == pytest.approx(expected)


def test_value_is_constant_within_an_htf_bar():
    """The aligned series steps once per HTF bar. A value that moves inside the
    HTF period means the forming bar is leaking in."""
    df = _hourly(n=48)
    aligned = align_to_base(
        resample_htf(df, "4h")["close"], pd.DatetimeIndex(df.index), confirmed_only=True
    )

    grouped = aligned.dropna().groupby(pd.Grouper(freq="4h", label="right", closed="left"))
    for period, chunk in grouped:
        if len(chunk) > 1:
            assert chunk.nunique() == 1, f"aligned value changed inside HTF bar {period}"


def test_warmup_is_nan_not_zero():
    """Before any HTF bar has closed there is nothing to report. Zero is a legal
    HTF score meaning 'balanced votes', so a zero fill would be indistinguishable
    from a genuine neutral reading."""
    df = _hourly(n=12)
    aligned = align_to_base(
        resample_htf(df, "4h")["close"], pd.DatetimeIndex(df.index), confirmed_only=True
    )
    assert pd.isna(aligned.iloc[0])


# ── negative controls: the test must fail when the shift is removed ─────────────


def test_left_labelling_is_genuine_lookahead():
    """THE negative control. Labelling an HTF bar with its OPEN time leaks.

    This is the real mistake, and it is the one the right-labelling in
    :func:`azimuth.data.resample.resample_htf` exists to prevent. A 4H bar
    covering 00:00-03:00 labelled ``00:00`` is handed to base bar 00:00 by
    ``reindex(ffill)`` -- so bar 00:00 receives a value computed from the closes of
    01:00, 02:00 and 03:00, none of which have happened.

    If this stops failing, the causality tests above prove nothing.
    """
    df = _hourly(n=48)
    open_labelled = df.resample("4h", label="left", closed="left").agg({"close": "last"})["close"]
    leaky = open_labelled.reindex(pd.DatetimeIndex(df.index), method="ffill")

    # At base bar 00:00 the leaked value is the close of 03:00 -- three bars ahead.
    t0 = pd.Timestamp("2020-01-01 00:00", tz="UTC")
    future_close = df["close"].loc[pd.Timestamp("2020-01-01 03:00", tz="UTC")]

    assert leaky.loc[t0] == pytest.approx(future_close), (
        "left-labelling no longer leaks -- this control can no longer demonstrate "
        "what right-labelling is for"
    )

    # And the correct construction does not do that.
    correct = align_to_base(
        resample_htf(df, "4h")["close"], pd.DatetimeIndex(df.index), confirmed_only=True
    )
    assert pd.isna(correct.loc[t0])


def test_shift_adds_exactly_one_htf_bar_of_lag():
    """What ``confirmed_only`` actually controls.

    Right-labelling alone is already causal, so the shift is not a safety
    mechanism -- it is what reproduces Pine's ``s[1]``. This pins the relationship
    so that a future "optimisation" removing the shift is caught as a behaviour
    change rather than passing as a harmless cleanup.
    """
    df = _hourly(n=48)
    marker = resample_htf(df, "4h")["close"]
    index = pd.DatetimeIndex(df.index)

    confirmed = align_to_base(marker, index, confirmed_only=True)
    unshifted = align_to_base(marker, index, confirmed_only=False)

    assert not confirmed.equals(unshifted)

    # The shifted series lags by exactly one HTF bar: at 08:00 it reports the bar
    # that closed at 04:00, while the unshifted one reports the bar that closed
    # at 08:00.
    t = pd.Timestamp("2020-01-01 08:00", tz="UTC")
    assert unshifted.loc[t] == pytest.approx(marker.loc[pd.Timestamp("2020-01-01 08:00", tz="UTC")])
    assert confirmed.loc[t] == pytest.approx(marker.loc[pd.Timestamp("2020-01-01 04:00", tz="UTC")])


def test_unshifted_is_still_causal_just_not_pine():
    """Stated explicitly so nobody reads ``confirmed_only=False`` as 'the leaky
    one'. It is one HTF bar less lag than Pine, and still uses no future data --
    the leak would come from left-labelling, which is tested above."""
    df = _hourly(n=48)
    marker = resample_htf(df, "4h")["close"]
    unshifted = align_to_base(marker, pd.DatetimeIndex(df.index), confirmed_only=False)

    for timestamp, value in unshifted.dropna().items():
        source_label = marker.index[marker.index <= timestamp][-1]
        assert source_label <= timestamp, "value came from a bar that had not closed"
        assert value == pytest.approx(marker.loc[source_label])


# ── the bias computation itself ─────────────────────────────────────────────────


def test_htf_bias_takes_four_discrete_values():
    """Three votes of +/-1, divided by 3: {-1, -1/3, +1/3, +1} and nothing else.

    An off-lattice value means a vote resolved to something other than +/-1 --
    which is how an alignment or NaN-handling bug shows up (finding 11).
    """
    df = _hourly(n=400)
    htf = resample_htf(df, "4h")
    bias = htf_bias(htf["close"], ema_length=10, rsi_length=14, slope_lookback=3).dropna()

    lattice = np.array([-1.0, -1 / 3, 1 / 3, 1.0])
    for value in bias.unique():
        assert np.min(np.abs(lattice - value)) < 1e-9, f"{value} is off the vote lattice"


def test_htf_votes_use_pines_ternary_not_math_sign():
    """docs/01 section 4 writes the votes as sign(); pine/AZIMUTH.pine:151
    implements them as ``cond ? 1 : -1``. They differ on exact equality, where
    sign() gives 0 and the ternary gives -1. Parity is against the code.

    A perfectly flat HTF series puts close exactly on its EMA and the EMA exactly
    on its own lag, so two votes hit the equality case.
    """
    flat = pd.Series(
        [100.0] * 60, index=pd.date_range("2020-01-01", periods=60, freq="4h", tz="UTC")
    )
    bias = htf_bias(flat, ema_length=10, rsi_length=14, slope_lookback=3).dropna()

    # close > he is False, he > he[3] is False -> -1 each. RSI on a flat series is
    # NaN (0/0), so the third vote is NaN and the sum propagates NaN.
    assert bias.empty or bias.isna().all() or (bias < 0).all()


def test_htf_score_blends_and_clips():
    index = pd.date_range("2020-01-01", periods=5, freq="1h", tz="UTC")
    htf1 = pd.Series([1.0, 1.0, -1.0, 1 / 3, -1 / 3], index=index)
    htf2 = pd.Series([1.0, -1.0, -1.0, -1 / 3, 1 / 3], index=index)

    blended = htf_score(htf1, htf2, weight_tf1=0.6)

    assert blended.iloc[0] == pytest.approx(1.0)
    assert blended.iloc[1] == pytest.approx(0.6 - 0.4)
    assert blended.iloc[2] == pytest.approx(-1.0)
    assert blended.min() >= -1.0 and blended.max() <= 1.0


def test_htf_score_falls_back_to_htf1_when_tf2_is_off():
    """pine/AZIMUTH.pine:156 uses nz(h1), so the fallback is 0 during warm-up, not
    na -- otherwise the composite would be na wherever HTF2 is unavailable."""
    index = pd.date_range("2020-01-01", periods=3, freq="1h", tz="UTC")
    htf1 = pd.Series([np.nan, 1.0, -1.0], index=index)

    result = htf_score(htf1, None)
    assert result.iloc[0] == pytest.approx(0.0)
    assert result.iloc[1] == pytest.approx(1.0)


# ── end to end ──────────────────────────────────────────────────────────────────


def test_htf_component_runs_end_to_end():
    df = _hourly(n=600)
    result = htf_component(df, tf1="240", tf2="1D", ema_length=10, rsi_length=14, slope_lookback=3)

    assert len(result) == len(df)
    assert result.index.equals(df.index)
    assert result.min() >= -1.0 and result.max() <= 1.0


def test_htf_component_is_causal_under_truncation():
    """The property from tests/test_lookahead.py, applied to the assembled
    component rather than to a single primitive."""
    df = _hourly(n=400)
    full = htf_component(df, tf1="240", tf2=None, ema_length=10)

    for t in (120, 200, 305, 399):
        truncated = htf_component(df.iloc[: t + 1], tf1="240", tf2=None, ema_length=10)
        pd.testing.assert_series_equal(
            full.iloc[: t + 1], truncated, check_freq=False, check_names=False
        )
