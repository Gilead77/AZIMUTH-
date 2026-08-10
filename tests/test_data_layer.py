"""Data layer: canonical frame validation, HTF resampling, cache keys.

``docs/04_SPEC_PYTHON_CLI.md`` sections 3, 5 and 6. The resampling tests here are
parity-critical -- ``tests/test_htf_alignment.py`` covers the lookahead contract
built on top of them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.data import cache, loaders
from azimuth.data.resample import bars_per_htf_bar, resample_htf, timeframe_to_rule


def _frame(n: int = 48, freq: str = "1h") -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=n, freq=freq, tz="UTC")
    close = np.arange(1.0, n + 1.0)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.ones(n),
        },
        index=index,
    )


# ── timeframe mapping ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("timeframe", "rule"),
    [
        ("15", "15min"),
        ("60", "60min"),
        ("240", "240min"),
        ("1D", "1D"),
        ("D", "1D"),
        ("1W", "1W"),
        ("W", "1W"),
        ("30S", "30s"),
        ("3M", "3MS"),
    ],
)
def test_timeframe_to_rule(timeframe: str, rule: str):
    assert timeframe_to_rule(timeframe) == rule


def test_months_map_to_month_start_not_month_end():
    """pandas' ``M`` anchors to month END. With label='right' that stamps a bar on
    the last day of the month it summarises rather than the first instant after
    it -- an off-by-one-bar alignment error, and invisible on a chart."""
    assert timeframe_to_rule("1M") == "1MS"


@pytest.mark.parametrize("bad", ["", "  ", "0", "-5", "4h", "1Y", "abc", "1x"])
def test_unrecognised_timeframes_raise(bad: str):
    """Guessing at an unknown timeframe would silently produce the wrong HTF."""
    with pytest.raises(ValueError):
        timeframe_to_rule(bad)


def test_bars_per_htf_bar_matches_docs_07_guidance():
    """docs/07 section 3: HTF1 ~4x the chart timeframe, HTF2 ~24x."""
    assert bars_per_htf_bar("60", "240") == pytest.approx(4.0)
    assert bars_per_htf_bar("60", "1D") == pytest.approx(24.0)
    assert bars_per_htf_bar("240", "1D") == pytest.approx(6.0)


def test_ratio_below_one_is_detectable():
    """A 'higher' timeframe faster than the chart defeats the confirmation
    contract entirely -- the caller needs to be able to see that."""
    assert bars_per_htf_bar("240", "60") < 1.0


# ── resampling ──────────────────────────────────────────────────────────────────


def test_htf_bar_contains_the_bars_tradingview_puts_in_it():
    """The grouping test. docs/11_FINDINGS.md finding 21.

    Base 1H closes are 1.0 .. 8.0 at 00:00 .. 07:00. TradingView's 4H bar starting
    00:00 covers the 1H bars 00:00-03:00, so open = 1.0 and close = 4.0. It is
    stamped 04:00 here -- the instant it closes, and the first timestamp at which
    its value could legally be known.
    """
    df = _frame(n=8, freq="1h")
    htf = resample_htf(df, "4h")

    assert htf.index[0] == pd.Timestamp("2020-01-01 04:00", tz="UTC")
    first = htf.iloc[0]
    assert first["open"] == pytest.approx(1.0)
    assert first["close"] == pytest.approx(4.0)
    assert first["high"] == pytest.approx(5.0)  # close 4.0 + 1.0
    assert first["low"] == pytest.approx(0.0)  # close 1.0 - 1.0

    second = htf.iloc[1]
    assert htf.index[1] == pd.Timestamp("2020-01-01 08:00", tz="UTC")
    assert second["open"] == pytest.approx(5.0)
    assert second["close"] == pytest.approx(8.0)


def test_spec_closed_right_takes_the_wrong_window():
    """Pins finding 21 so the spec's snippet cannot be pasted back in.

    ``closed="right"`` builds (00:00, 04:00], which aggregates 1H bars
    01:00-04:00: it drops the bar that opens the HTF period and swallows one that
    belongs to the next. Every OHLC field then comes from the wrong window.
    """
    df = _frame(n=8, freq="1h")
    correct = resample_htf(df, "4h")

    spec_version = df.resample("4h", label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )

    assert spec_version.loc[pd.Timestamp("2020-01-01 04:00", tz="UTC"), "close"] == pytest.approx(
        5.0
    ), "closed='right' pulls in the 04:00 bar, which belongs to the next HTF period"
    assert correct.loc[pd.Timestamp("2020-01-01 04:00", tz="UTC"), "close"] == pytest.approx(4.0)


def test_daily_bar_covers_one_calendar_day():
    """The same error is easiest to see at the daily boundary: with
    closed='right', the 00:00 bar of a day lands in the PREVIOUS day's bar."""
    df = _frame(n=24, freq="1h")  # a full day, 00:00 .. 23:00
    htf = resample_htf(df, "1D")

    assert len(htf) == 1, "24 hourly bars are exactly one daily bar"
    row = htf.iloc[0]
    assert htf.index[0] == pd.Timestamp("2020-01-02 00:00", tz="UTC"), "stamped at its close"
    assert row["open"] == pytest.approx(df["open"].iloc[0])
    assert row["high"] == pytest.approx(df["high"].max())
    assert row["low"] == pytest.approx(df["low"].min())
    assert row["close"] == pytest.approx(df["close"].iloc[-1])
    assert row["volume"] == pytest.approx(df["volume"].sum())


def test_empty_periods_are_dropped_not_emitted_as_nan():
    """Pine has no bar where the instrument did not trade. A NaN row would
    forward-fill into the base timeframe as a real HTF reading."""
    index = pd.DatetimeIndex(["2020-01-01 00:00", "2020-01-01 01:00", "2020-01-10 00:00"], tz="UTC")
    df = pd.DataFrame(
        {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0}, index=index
    )

    htf = resample_htf(df, "1D")
    assert htf["close"].notna().all()
    assert len(htf) == 2, "one bar per day that actually traded, not one per calendar day"


def test_resample_rejects_a_non_monotonic_index():
    df = _frame(n=8)
    shuffled = df.iloc[[3, 1, 2, 0, 4, 5, 6, 7]]
    with pytest.raises(ValueError, match="monotonic"):
        resample_htf(shuffled, "4h")


def test_resample_rejects_missing_columns():
    df = _frame(n=8).drop(columns=["volume"])
    with pytest.raises(ValueError, match="missing OHLCV"):
        resample_htf(df, "4h")


# ── canonical frame validation ──────────────────────────────────────────────────


def test_valid_frame_passes():
    assert loaders.validate_frame(_frame()) is not None


def test_naive_index_is_rejected():
    df = _frame()
    df.index = df.index.tz_localize(None)
    with pytest.raises(ValueError, match="tz-aware"):
        loaders.validate_frame(df)


def test_non_utc_index_is_rejected():
    df = _frame()
    df.index = df.index.tz_convert("America/New_York")
    with pytest.raises(ValueError, match="UTC"):
        loaders.validate_frame(df)


def test_duplicate_timestamps_are_rejected():
    df = _frame(n=4)
    df = pd.concat([df, df.iloc[[2]]]).sort_index()
    with pytest.raises(ValueError, match="duplicate"):
        loaders.validate_frame(df)


def test_nan_in_ohlc_is_rejected():
    df = _frame()
    df.iloc[5, df.columns.get_loc("close")] = np.nan
    with pytest.raises(ValueError, match="NaN in OHLC"):
        loaders.validate_frame(df)


def test_high_below_close_is_rejected():
    """A vendor artefact that silently inverts true range on that bar, perturbing
    ATR and every ATR-anchored stop for the next `length` bars."""
    df = _frame()
    df.iloc[5, df.columns.get_loc("high")] = df.iloc[5]["close"] - 1.0
    with pytest.raises(ValueError, match="OHLC invariants"):
        loaders.validate_frame(df)


def test_low_above_open_is_rejected():
    df = _frame()
    df.iloc[7, df.columns.get_loc("low")] = df.iloc[7]["open"] + 1.0
    with pytest.raises(ValueError, match="OHLC invariants"):
        loaders.validate_frame(df)


def test_gap_report_is_emitted_but_not_fatal(capsys):
    """docs/04 section 5: gaps go to stderr. They are normal, but they matter --
    docs/05 section 2's embargo is measured in bars, so a gap means it covers less
    wall-clock time than intended."""
    df = _frame(n=6)
    df = df.drop(index=df.index[3])

    loaders.validate_frame(df, timeframe="60")
    assert "[gap]" in capsys.readouterr().err


def test_no_gap_report_on_an_even_index(capsys):
    loaders.validate_frame(_frame(n=10), timeframe="60")
    assert capsys.readouterr().err == ""


def test_csv_round_trip(tmp_path):
    df = _frame(n=10)
    path = tmp_path / "ohlcv.csv"
    df.to_csv(path, index_label="time")

    loaded = loaders.load_csv(path, symbol="TEST", timeframe="60")
    assert loaded.attrs["symbol"] == "TEST"
    assert list(loaded.columns) == list(loaders.OHLCV_COLUMNS)
    pd.testing.assert_series_equal(
        loaded["close"], df["close"], check_freq=False, check_names=False
    )
    assert loaded.index.equals(df.index)


# ── cache ───────────────────────────────────────────────────────────────────────


def test_cache_key_is_filesystem_safe_and_collision_resistant():
    """Symbols contain / and : -- sanitising alone would collide."""
    a = cache.cache_key("BTC/USDT", "240", "2018-01-01", "2026-01-01")
    b = cache.cache_key("BTC:USDT", "240", "2018-01-01", "2026-01-01")

    assert a != b
    for key in (a, b):
        assert "/" not in key and ":" not in key


def test_cache_key_is_deterministic():
    args = ("TVC:DXY", "1D", "2018-01-01", "2026-01-01")
    assert cache.cache_key(*args) == cache.cache_key(*args)


def test_cache_round_trip(tmp_path):
    df = _frame(n=20)
    key = cache.cache_key("TEST", "60", "2020-01-01", "2020-01-02")

    assert cache.read(tmp_path, key) is None
    cache.write(tmp_path, key, df)
    # parquet does not round-trip the index freq attribute; contents are what matter
    pd.testing.assert_frame_equal(cache.read(tmp_path, key), df, check_freq=False)


def test_data_hash_ignores_attrs():
    """fetched_at changes on every download. Two identical datasets fetched an
    hour apart must hash the same, or docs/04 section 8's determinism test can
    never pass."""
    a = _frame(n=20)
    b = _frame(n=20)
    a.attrs["fetched_at"] = "2026-01-01T00:00:00Z"
    b.attrs["fetched_at"] = "2026-06-01T12:00:00Z"

    assert cache.data_sha256(a) == cache.data_sha256(b)


def test_data_hash_changes_when_history_is_revised():
    """A vendor silently revising history must invalidate a 'reproduction'."""
    a = _frame(n=20)
    b = _frame(n=20)
    b.iloc[10, b.columns.get_loc("close")] += 1e-9

    assert cache.data_sha256(a) != cache.data_sha256(b)
