"""The parity harness, tested against a synthetic fixture.

The real fixture arrives from TradingView after the indicator is compile-checked,
so until then the harness itself is the thing that can be verified: a fixture
generated from our own pipeline must pass at 1e-6, and a fixture perturbed by
more than the tolerance must fail.

That round-trip exercises everything except agreement with Pine -- CSV parsing,
title-decoration stripping, burn-in, per-series tolerances, the ``x_htf`` lattice
check, NaN-pattern comparison and signal-bar set equality. Without it, the first
run against a real export would be testing the harness and the indicator at the
same time, and a harness bug would read as a parity failure.

Same reasoning as the planted leaks in ``tests/test_lookahead.py`` and the
positive control proposed for the validation harness in docs/11_FINDINGS.md
finding 10: a checking tool that has never been shown to fail is not evidence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.config.schema import load_default
from azimuth.core.pipeline import compute_frame
from azimuth.validate.parity import (
    BURN_IN_BARS,
    TOLERANCES,
    compare,
    htf_lattice_violations,
    load_pine_export,
    run_parity,
)

# Short enough to run fast, long enough that 283 burn-in bars still leave a
# usable sample and the daily HTF EMA can seed.
N_BARS = 2000

CONFIG = load_default()
CONFIG = CONFIG.model_copy(
    update={
        "ribbon": CONFIG.ribbon.model_copy(update={"lengths": (5, 8, 13, 21, 34, 55, 89, 144)}),
        "htf": CONFIG.htf.model_copy(update={"ema_length": 20}),
    }
)


def _ohlcv(seed: int = 42, n: int = N_BARS) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.8, n))
    return pd.DataFrame(
        {
            "open": close + rng.normal(0.0, 0.1, n),
            "high": close + np.abs(rng.normal(0.0, 0.6, n)) + 0.3,
            "low": close - np.abs(rng.normal(0.0, 0.6, n)) - 0.3,
            "close": close,
            "volume": rng.uniform(100.0, 1000.0, n),
        },
        index=pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC"),
    )


def _write_fixture(path, df: pd.DataFrame, computed: pd.DataFrame, decorate: bool = True) -> None:
    """Write a CSV shaped like TradingView's 'Export chart data'.

    ``decorate=True`` reproduces the indicator-name suffix TradingView appends to
    plot titles, so the parser's normalisation is exercised rather than assumed.
    """
    out = pd.DataFrame(index=df.index)
    for column in ("open", "high", "low", "close", "volume"):
        out[column] = df[column]
    for column in TOLERANCES:
        if column in computed.columns:
            name = f"{column} (AZIMUTH — Composite Signal Engine)" if decorate else column
            out[name] = computed[column]

    out.index.name = "time"
    out.to_csv(path)


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    """A fixture CSV generated from our own pipeline, plus the frame behind it."""
    df = _ohlcv()
    computed = compute_frame(df, CONFIG)
    path = tmp_path_factory.mktemp("parity") / "AZIMUTH_SYNTH_1h.csv"
    _write_fixture(path, df, computed)
    return path, df, computed


# ── parsing ─────────────────────────────────────────────────────────────────────


def test_export_parser_strips_tradingview_title_decoration(synthetic):
    path, _, _ = synthetic
    parsed = load_pine_export(path)

    assert "x_ribbon" in parsed.columns
    assert "x_state" in parsed.columns
    assert not any("AZIMUTH" in str(c) for c in parsed.columns)


def test_export_parser_produces_a_utc_index(synthetic):
    path, df, _unused = synthetic
    parsed = load_pine_export(path)

    assert isinstance(parsed.index, pd.DatetimeIndex)
    assert str(parsed.index.tz) == "UTC"
    assert parsed.index.is_monotonic_increasing
    assert len(parsed) == len(df)


def test_export_without_x_series_is_refused(tmp_path):
    """docs/03 section 4 requires the display.data_window exports. Without them
    there is nothing to compare, and a silent pass would be the worst outcome."""
    path = tmp_path / "bare.csv"
    _ohlcv(n=50).to_csv(path, index_label="time")

    with pytest.raises(ValueError, match=r"no x_\* series"):
        load_pine_export(path)


# ── the round trip ──────────────────────────────────────────────────────────────


def test_a_fixture_from_our_own_pipeline_passes(synthetic):
    """Trivially true by construction -- which is the point. If this fails, the
    harness is broken, not the indicator."""
    path, _, _ = synthetic
    report = run_parity(path, CONFIG)

    assert report.passed, "\n".join(str(r) for r in report.results if not r.passed)
    assert report.n_compared == N_BARS - BURN_IN_BARS


def test_every_expected_series_is_actually_compared(synthetic):
    path, _, _computed = synthetic
    report = run_parity(path, CONFIG)

    compared = {r.series for r in report.results}
    for name in ("x_ribbon", "x_bb", "x_rsi", "x_htf", "x_er", "x_adx", "x_pctb", "x_state"):
        assert name in compared, f"{name} was not compared"
    assert "signal_bars" in compared, "docs/06 section 2 asks for trigger-bar set equality"


def test_burn_in_is_283_bars(synthetic):
    """docs/06 section 2: max(233, 200, 60) + 50."""
    assert BURN_IN_BARS == 283
    path, _, _ = synthetic
    report = run_parity(path, CONFIG)
    assert report.n_bars - report.n_compared == 283


def test_too_few_bars_is_refused(tmp_path):
    df = _ohlcv(n=100)
    computed = compute_frame(df, CONFIG)
    path = tmp_path / "short.csv"
    _write_fixture(path, df, computed)

    with pytest.raises(ValueError, match="burn-in"):
        run_parity(path, CONFIG)


# ── negative controls: the harness must fail when it should ─────────────────────


@pytest.mark.parametrize(
    ("series", "perturbation"),
    [
        ("x_ribbon", 1e-4),
        ("x_bb", 1e-4),
        ("x_rsi", 1e-3),
        ("x_er", 1e-3),
        ("x_pctb", 1e-4),
    ],
)
def test_a_perturbation_above_tolerance_fails(tmp_path, series: str, perturbation: float):
    """The control that gives the passing test above its meaning."""
    df = _ohlcv()
    computed = compute_frame(df, CONFIG)
    computed = computed.copy()
    computed[series] = computed[series] + perturbation

    path = tmp_path / f"perturbed_{series}.csv"
    _write_fixture(path, df, computed)

    report = run_parity(path, CONFIG)
    assert not report.passed
    failed = {r.series for r in report.results if not r.passed}
    assert series in failed, f"perturbing {series} by {perturbation} was not caught"


def test_a_perturbation_below_tolerance_passes(tmp_path):
    """The tolerance is a real threshold, not a rubber stamp in either direction."""
    df = _ohlcv()
    computed = compute_frame(df, CONFIG).copy()
    computed["x_ribbon"] = computed["x_ribbon"] + 1e-9  # under the 1e-6 tolerance

    path = tmp_path / "tiny.csv"
    _write_fixture(path, df, computed)

    assert run_parity(path, CONFIG).passed


def test_a_single_state_disagreement_fails(tmp_path):
    """x_state is compared EXACTLY, bar for bar (docs/06 section 2). One bar is
    enough, and it must also show up as a signal-bar mismatch."""
    df = _ohlcv()
    computed = compute_frame(df, CONFIG).copy()
    position = len(computed) - 100
    computed.iloc[position, computed.columns.get_loc("x_state")] = 1

    path = tmp_path / "state.csv"
    _write_fixture(path, df, computed)

    report = run_parity(path, CONFIG)
    failed = {r.series for r in report.results if not r.passed}

    assert "x_state" in failed
    assert "signal_bars" in failed, "a changed state must move a trigger bar too"


def test_a_shifted_series_fails_even_though_the_values_are_identical(tmp_path):
    """The alignment failure mode. A one-bar shift preserves every value and the
    whole distribution, so anything comparing summary statistics would pass it.

    This is what an HTF grouping or shift error looks like (findings 11 and 21).
    """
    df = _ohlcv()
    computed = compute_frame(df, CONFIG).copy()
    computed["x_ribbon"] = computed["x_ribbon"].shift(1)

    path = tmp_path / "shifted.csv"
    _write_fixture(path, df, computed)

    report = run_parity(path, CONFIG)
    assert not report.passed
    assert "x_ribbon" in {r.series for r in report.results if not r.passed}


def test_nan_pattern_mismatch_fails_even_when_values_agree(tmp_path):
    """A value present on one side and absent on the other is a warm-up
    misalignment. max|delta| over the overlap would hide it entirely."""
    df = _ohlcv()
    computed = compute_frame(df, CONFIG).copy()
    position = len(computed) - 50
    computed.iloc[position, computed.columns.get_loc("x_rsi")] = np.nan

    path = tmp_path / "nan.csv"
    _write_fixture(path, df, computed)

    report = run_parity(path, CONFIG)
    result = next(r for r in report.results if r.series == "x_rsi")
    assert not result.passed
    assert "na on one side" in result.detail


# ── the x_htf lattice assertion (finding 11) ────────────────────────────────────


def test_htf_lattice_accepts_valid_blends():
    votes = (-1.0, -1 / 3, 1 / 3, 1.0)
    valid = pd.Series([0.6 * a + 0.4 * b for a in votes for b in votes]).clip(-1.0, 1.0)
    assert htf_lattice_violations(valid) == []


def test_htf_lattice_tolerates_float_noise():
    """The reason docs/06's 'exact' had to be relaxed: 0.6*(1/3)+0.4*(1/3) is not
    representable in binary64."""
    votes = (-1.0, -1 / 3, 1 / 3, 1.0)
    noisy = pd.Series([0.6 * a + 0.4 * b + 1e-13 for a in votes for b in votes]).clip(-1.0, 1.0)
    assert htf_lattice_violations(noisy) == []


def test_htf_lattice_rejects_off_lattice_values():
    """An alignment bug produces values between the vote points -- the lattice
    points are ~0.13 apart, so this cannot be float noise."""
    problems = htf_lattice_violations(pd.Series([0.0, 0.5, 0.123]))
    assert problems
    assert "off-lattice" in " ".join(problems)


def test_htf_lattice_rejects_too_many_distinct_values():
    """A continuous x_htf means it was not built from two three-way votes."""
    problems = htf_lattice_violations(pd.Series(np.linspace(-1.0, 1.0, 200)))
    assert problems


def test_zero_is_on_the_lattice_because_pine_emits_it():
    """pine/AZIMUTH.pine:156 falls back to ``nz(h1)``, so 0 is a legal x_htf value
    during the warm-up -- and it is NOT otherwise reachable, since ``0.6a = -0.4b``
    has no solution in the vote set. Excluding it would flag correct output."""
    assert htf_lattice_violations(pd.Series([0.0])) == []


def test_real_pipeline_htf_sits_on_the_lattice(synthetic):
    _, _, computed = synthetic
    assert htf_lattice_violations(computed["x_htf"]) == []


def test_an_htf_that_never_seeded_is_caught(tmp_path):
    """Because 0 is legal, the lattice check alone cannot catch an x_htf that is
    zero all the way through -- which is what happens when the resample yields too
    few HTF bars for htf.ema_length. The highest-weighted component would then be
    contributing nothing, silently."""
    df = _ohlcv()
    computed = compute_frame(df, CONFIG).copy()
    computed["x_htf"] = 0.0

    path = tmp_path / "dead_htf.csv"
    _write_fixture(path, df, computed)

    report = run_parity(path, CONFIG)
    result = next(r for r in report.results if r.series == "x_htf")
    assert not result.passed
    assert "never seeded" in result.detail


# ── missing series ──────────────────────────────────────────────────────────────


def test_absent_series_are_reported_not_silently_skipped(tmp_path):
    """A fixture exported before finding 19 has no x_ref*/x_rho*. Those must be
    listed as not-compared rather than quietly passing."""
    df = _ohlcv()
    computed = compute_frame(df, CONFIG)
    path = tmp_path / "no_refs.csv"
    _write_fixture(path, df, computed)

    report = run_parity(path, CONFIG)
    assert "x_ref1" in report.missing
    assert "x_rho1" in report.missing
    assert report.passed, "missing optional series must not fail the gate"


def test_tol_override_applies_to_every_series(tmp_path):
    df = _ohlcv()
    computed = compute_frame(df, CONFIG).copy()
    computed["x_ribbon"] = computed["x_ribbon"] + 1e-4

    path = tmp_path / "override.csv"
    _write_fixture(path, df, computed)

    assert not run_parity(path, CONFIG).passed
    assert run_parity(path, CONFIG, tol=1e-2).passed


def test_compare_requires_overlapping_index(synthetic):
    path, _df, computed = synthetic
    pine = load_pine_export(path)
    elsewhere = computed.copy()
    elsewhere.index = elsewhere.index + pd.Timedelta(days=3650)

    with pytest.raises(ValueError, match="overlapping bars"):
        compare(pine, elsewhere)
