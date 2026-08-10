"""THE most important test in the repo (``docs/06_PARITY_TESTS.md`` section 4).

The property, stated once::

    For any input series and any truncation point t, computing a primitive on
    series[:t+1] must yield values identical to the full-series result at every
    index <= t.

This is causality. A primitive that violates it has used information from a bar
that had not happened yet, and every performance number downstream of it is a
lie. CLAUDE.md rule 1 admits no exceptions, and this test is what makes the rule
enforceable rather than aspirational.

Two design choices worth stating:

* **Exact equality, not a tolerance.** Truncating the input does not change the
  sequence of arithmetic operations applied to bars <= t, so the results should
  be bit-identical. Any primitive needing slack here is doing something
  length-dependent, which is itself suspicious. Where pandas' internal rolling
  accumulators genuinely require slack it is declared per-primitive and stays
  many orders of magnitude tighter than the 1e-6 parity gate.

* **A negative control.** ``test_the_harness_catches_a_planted_leak`` runs a
  deliberately non-causal function through the same machinery and asserts it
  FAILS. Without it, a bug in the comparison helper would make every other test
  in this file pass vacuously -- which is the same reasoning as finding 10's
  positive control for the validation harness, applied to the test itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from azimuth.core import primitives as p

# ── input generation ────────────────────────────────────────────────────────────

MIN_BARS = 40
MAX_BARS = 120

_price = st.floats(min_value=1.0, max_value=10_000.0, allow_nan=False, allow_infinity=False)
_frac = st.floats(min_value=0.0, max_value=0.05, allow_nan=False, allow_infinity=False)


@st.composite
def ohlc_frames(draw: st.DrawFn) -> pd.DataFrame:
    """A valid OHLCV frame plus a second correlated series, per docs/04 section 5.

    Invariants held: ``high >= max(open, close)``, ``low <= min(open, close)``.
    """
    n = draw(st.integers(min_value=MIN_BARS, max_value=MAX_BARS))
    close = np.asarray(draw(st.lists(_price, min_size=n, max_size=n)), dtype=float)
    open_ = np.asarray(draw(st.lists(_price, min_size=n, max_size=n)), dtype=float)
    up = np.asarray(draw(st.lists(_frac, min_size=n, max_size=n)), dtype=float)
    down = np.asarray(draw(st.lists(_frac, min_size=n, max_size=n)), dtype=float)
    ref = np.asarray(draw(st.lists(_price, min_size=n, max_size=n)), dtype=float)

    hi_base = np.maximum(open_, close)
    lo_base = np.minimum(open_, close)
    high = hi_base * (1.0 + up)
    low = lo_base * (1.0 - down)

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.ones(n),
            "ref": ref,
        },
        index=pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC"),
    )


# ── the primitive registry ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Case:
    """One primitive, bound to short lookback lengths so short series still
    produce values to compare."""

    name: str
    fn: Callable[[pd.DataFrame], Any]
    atol: float = 0.0
    rtol: float = 0.0
    note: str = field(default="")


CASES: list[Case] = [
    Case("sma", lambda d: p.sma(d["close"], 5)),
    Case("ema", lambda d: p.ema(d["close"], 5)),
    Case("rma", lambda d: p.rma(d["close"], 5)),
    Case("rsi", lambda d: p.rsi(d["close"], 5)),
    Case("stdev", lambda d: p.stdev(d["close"], 5)),
    Case("true_range", lambda d: p.true_range(d["high"], d["low"], d["close"])),
    Case("atr", lambda d: p.atr(d["high"], d["low"], d["close"], 5)),
    Case("percentrank", lambda d: p.percentrank(d["close"], 5)),
    # pandas' rolling correlation uses a running accumulator whose partial sums
    # depend on how much data precedes the window, so truncation can perturb the
    # last bits. Still ~6 orders of magnitude tighter than the parity gate.
    Case(
        "correlation",
        lambda d: p.correlation(d["close"], d["ref"], 10),
        atol=1e-12,
        note="pandas rolling accumulator",
    ),
    Case("dmi", lambda d: p.dmi(d["high"], d["low"], d["close"], 5, 5)),
    Case("pivot_high", lambda d: p.pivot_high(d["close"], 3, 3)),
    Case("pivot_low", lambda d: p.pivot_low(d["close"], 3, 3)),
    Case("change", lambda d: p.change(d["close"])),
    Case("rolling_sum", lambda d: p.rolling_sum(d["close"], 5)),
    Case("crossover", lambda d: p.crossover(d["close"], p.sma(d["close"], 5))),
    Case("crossunder", lambda d: p.crossunder(d["close"], p.sma(d["close"], 5))),
    Case("fixnan", lambda d: p.fixnan(p.pivot_high(d["close"], 3, 3))),
    Case(
        "valuewhen",
        lambda d: p.valuewhen(p.crossover(d["close"], p.sma(d["close"], 5)), d["close"], 0),
    ),
]

CASES_BY_NAME = {c.name: c for c in CASES}


# ── comparison ──────────────────────────────────────────────────────────────────


def _as_arrays(result: Any) -> list[np.ndarray]:
    """Normalise a primitive's return into a list of float arrays.

    ``dmi`` returns a 3-tuple; everything else returns one Series. Booleans are
    cast to float so one comparison path covers both.
    """
    parts = result if isinstance(result, tuple) else (result,)
    return [np.asarray(part, dtype=float) for part in parts]


def causality_violations(full: Any, truncated: Any, t: int, case: Case) -> list[str]:
    """Return a description of every way ``truncated`` disagrees with ``full[:t+1]``.

    Empty list means the primitive is causal for this input and truncation point.
    """
    problems: list[str] = []
    full_parts = _as_arrays(full)
    trunc_parts = _as_arrays(truncated)

    if len(full_parts) != len(trunc_parts):
        return [f"arity changed: {len(full_parts)} vs {len(trunc_parts)}"]

    for k, (a_full, a_trunc) in enumerate(zip(full_parts, trunc_parts, strict=True)):
        a = a_full[: t + 1]
        b = a_trunc

        if a.shape != b.shape:
            problems.append(f"part {k}: length {a.shape} vs {b.shape}")
            continue

        # The NaN pattern is part of the contract: a value that was NaN on the
        # full series must still be NaN when the future is removed, and vice
        # versa. A primitive that "fills in" a NaN once later bars arrive has
        # read the future.
        nan_a, nan_b = np.isnan(a), np.isnan(b)
        if not np.array_equal(nan_a, nan_b):
            first = int(np.flatnonzero(nan_a != nan_b)[0])
            problems.append(
                f"part {k}: NaN pattern differs at index {first} "
                f"(full={'NaN' if nan_a[first] else 'value'}, "
                f"truncated={'NaN' if nan_b[first] else 'value'})"
            )
            continue

        both = ~nan_a
        if not np.allclose(a[both], b[both], atol=case.atol, rtol=case.rtol, equal_nan=False):
            diffs = np.abs(a[both] - b[both])
            worst = int(np.argmax(diffs))
            problems.append(
                f"part {k}: value differs, max |delta| = {diffs.max():.3e} at masked index {worst}"
            )

    return problems


# ── the property ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
@given(frame=ohlc_frames(), cut=st.floats(min_value=0.0, max_value=1.0))
@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_truncating_the_input_never_changes_the_past(
    case: Case, frame: pd.DataFrame, cut: float
) -> None:
    """Truncating at bar t must not change any value at bars <= t.

    ``cut`` is a fraction so hypothesis explores truncation points across the
    whole series rather than clustering at one end.
    """
    n = len(frame)
    t = int(cut * (n - 1))

    full = case.fn(frame)
    truncated = case.fn(frame.iloc[: t + 1])

    problems = causality_violations(full, truncated, t, case)
    assert not problems, (
        f"LOOKAHEAD in {case.name}: truncating at bar {t} of {n} changed the past.\n"
        + "\n".join(f"  - {p_}" for p_ in problems)
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_every_prefix_agrees_on_a_fixed_series(case: Case) -> None:
    """Exhaustive version: check EVERY truncation point on one deterministic series.

    The hypothesis test samples truncation points; this one leaves none out. A
    lookahead that only bites at a specific offset -- an off-by-one in a pivot
    confirmation, say -- would slip past sampling but not past this.
    """
    rng = np.random.default_rng(20260810)
    n = 80
    close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, n))
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + np.abs(rng.normal(0.0, 0.5, n)),
            "low": close - np.abs(rng.normal(0.0, 0.5, n)),
            "close": close,
            "volume": np.ones(n),
            "ref": 50.0 + np.cumsum(rng.normal(0.0, 1.0, n)),
        },
        index=pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC"),
    )

    full = case.fn(frame)
    for t in range(n):
        problems = causality_violations(full, case.fn(frame.iloc[: t + 1]), t, case)
        assert not problems, f"LOOKAHEAD in {case.name} at truncation t={t}:\n" + "\n".join(
            f"  - {p_}" for p_ in problems
        )


# ── negative control: the harness must have teeth ───────────────────────────────


def _leaky_next_bar(frame: pd.DataFrame) -> pd.Series:
    """A deliberately non-causal 'primitive': tomorrow's close, today.

    This is the cheating control of docs/11_FINDINGS.md finding 10, scaled down to
    a single function. If the machinery above cannot catch this, it cannot catch
    anything, and every passing test in this file is vacuous.
    """
    return frame["close"].shift(-1)


def _leaky_centred_mean(frame: pd.DataFrame) -> pd.Series:
    """A subtler leak: a centred rolling mean. Reads three bars ahead."""
    return frame["close"].rolling(7, center=True).mean()


@pytest.mark.parametrize("leak", [_leaky_next_bar, _leaky_centred_mean])
def test_the_harness_catches_a_planted_leak(leak: Callable[[pd.DataFrame], pd.Series]) -> None:
    """The comparison must FAIL on a known-non-causal function."""
    rng = np.random.default_rng(1)
    n = 60
    close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, n))
    frame = pd.DataFrame(
        {"close": close}, index=pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC")
    )
    case = Case("planted-leak", leak)

    full = leak(frame)
    # Cut well inside the series so the leak has future bars to read on the full
    # series and none on the truncated one.
    t = n // 2
    problems = causality_violations(full, leak(frame.iloc[: t + 1]), t, case)

    assert problems, (
        "the lookahead harness failed to detect a planted leak — every other test "
        "in this file is therefore meaningless"
    )


# ── the specific lookahead traps this project is most likely to hit ─────────────


def test_pivot_confirmation_is_lagged_not_centred() -> None:
    """docs/01 section 3.2 and docs/06 section 3: pivots confirm ``legs`` bars late.

    That lag is REPRODUCED, not removed. The value is stamped at the confirmation
    bar and reads back to the pivot bar; a centred implementation that stamps it
    at the pivot bar is lookahead and is what this asserts against.
    """
    close = pd.Series([1.0, 2.0, 3.0, 9.0, 3.0, 2.0, 1.0, 2.0, 3.0])
    #                  0    1    2    3(pivot) 4    5    6    7    8
    piv = p.pivot_high(close, 3, 3)

    # Nothing may be known before the confirmation bar at index 3 + 3 = 6.
    assert piv.iloc[:6].isna().all(), "pivot was stamped before it could be confirmed"
    assert piv.iloc[6] == 9.0, "pivot value must appear at the confirmation bar"


def test_ema_is_not_seeded_from_the_whole_series() -> None:
    """A seed computed from the full series mean would be lookahead in disguise.

    Pine seeds with the SMA of the FIRST ``length`` bars, which is causal. This
    pins that the seed value depends only on bars 0..length-1.
    """
    src = pd.Series([1.0] * 5 + [1000.0] * 20)
    seeded = p.ema(src, 5)
    assert seeded.iloc[4] == pytest.approx(1.0), (
        "the EMA seed must be the SMA of the first 5 bars only — a seed reflecting "
        "the later 1000.0 values would mean the whole series was consulted"
    )


def test_state_dependent_primitives_do_not_backfill() -> None:
    """``fixnan`` forward-fills. It must never backward-fill.

    docs/06 section 3: na propagates; never fill with 0 — and never fill from the
    future, which is the failure mode that would look like a harmless convenience.
    """
    src = pd.Series([np.nan, np.nan, 5.0, np.nan, np.nan, 7.0, np.nan])
    filled = p.fixnan(src)

    assert filled.iloc[:2].isna().all(), "fixnan back-filled from a future value"
    assert filled.iloc[2] == 5.0
    assert filled.iloc[3] == 5.0 and filled.iloc[4] == 5.0
    assert filled.iloc[5] == 7.0
    assert filled.iloc[6] == 7.0
