"""Pine <-> Python parity harness. Implements ``docs/06_PARITY_TESTS.md``.

THE GATE. If Pine and Python disagree, every validation result is worthless -- you
would be validating a different system from the one that trades. Parity is a gate,
not a nice-to-have (docs/06 preamble, CLAUDE.md rule 2).

Assertions (docs/06 section 2, plus the series added by finding 19):

=================================  =========  ==============================
Series                             Tolerance  Notes
=================================  =========  ==============================
``x_ribbon``                       1e-6       EMA seeding must match
``x_bb``, ``x_pctb``, ``x_bwpct``  1e-6       stdev is population, ddof=0
``x_rsi``                          1e-5       RMA seeding differs in burn-in
``x_htf``                          1e-9       finding 11, see below
``x_corr``, ``x_rho*``             1e-5
``x_ref*``                         1e-6       raw reference prices
``x_er``, ``x_adx``                1e-5
``x_crowd``                        1e-6
``x_state``                        exact      integer, bar for bar
Signal bar indices                 exact      set equality of trigger times
=================================  =========  ==============================

Burn-in: discard the first ``max(233, 200, 60) + 50 = 283`` bars before comparing.

FINDING 11 -- docs/06 sets ``x_htf`` to "exact", but
``htfScore = clip(0.6*h1 + 0.4*h2)`` with each ``h`` in {-1, -1/3, +1/3, +1}, and
``0.6*(1/3)`` is not representable in binary64 (it evaluates to
0.19999999999999998). Strict equality fails on CORRECT code. Compared at 1e-9
instead, plus the assertion "exact" was actually reaching for: every value must
sit on the 16-point lattice ``{0.6a + 0.4b}``. Alignment bugs produce off-lattice
values, so the lattice check catches what strict equality was meant to catch
without failing on float noise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from azimuth.config.schema import AzimuthConfig
from azimuth.core._types import FloatSeries
from azimuth.core.pipeline import compute_frame

__all__ = [
    "BURN_IN_BARS",
    "TOLERANCES",
    "ParityReport",
    "ParityResult",
    "compare",
    "htf_lattice_violations",
    "load_pine_export",
    "run_parity",
]

BURN_IN_BARS = 283
"""max(233, 200, 60) + 50 (docs/06 section 2).

The 233 is the slowest ribbon EMA, 200 the percentrank lookbacks, 60 the
correlation window. The +50 is slack for the RMA seeding differences docs/06
section 2 flags on ``x_rsi``.
"""

TOLERANCES: dict[str, float] = {
    "x_ribbon": 1e-6,
    "x_bb": 1e-6,
    "x_pctb": 1e-6,
    "x_bwpct": 1e-6,
    "x_rsi": 1e-5,
    "x_htf": 1e-9,  # finding 11: "exact" fails on correct code
    "x_corr": 1e-5,
    "x_er": 1e-5,
    "x_adx": 1e-5,
    "x_state": 0.0,  # integer state machine, exact
    # Added by finding 19 so the correlation chain is verifiable at all.
    "x_ref1": 1e-6,
    "x_ref2": 1e-6,
    "x_ref3": 1e-6,
    "x_rho1": 1e-5,
    "x_rho2": 1e-5,
    "x_rho3": 1e-5,
    "x_crowd": 1e-6,
}

_HTF_VOTES = (-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0)


@dataclass(frozen=True)
class ParityResult:
    """Per-series comparison outcome."""

    series: str
    tolerance: float
    max_abs_diff: float
    n_compared: int
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        return (
            f"{verdict} {self.series:<10} max|delta|={self.max_abs_diff:.3e} "
            f"tol={self.tolerance:.0e} n={self.n_compared}"
            + (f"  {self.detail}" if self.detail else "")
        )


@dataclass(frozen=True)
class ParityReport:
    """The whole comparison."""

    results: list[ParityResult]
    n_bars: int
    n_compared: int
    missing: list[str]

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(r.passed for r in self.results)


def _normalise(name: str) -> str:
    """TradingView decorates exported plot titles.

    A column may arrive as ``x_ribbon``, ``AZIMUTH: x_ribbon`` or
    ``x_ribbon (AZIMUTH — Composite Signal Engine)`` depending on export path and
    locale. Reduce to the bare ``x_*`` token so the comparison does not depend on
    which of those the user happened to produce.
    """
    match = re.search(r"(x_[a-z0-9_]+)", name.strip(), flags=re.IGNORECASE)
    return match.group(1).lower() if match else name.strip().lower()


def load_pine_export(path: str | Path) -> pd.DataFrame:
    """Parse a TradingView 'Export chart data' CSV.

    Returns a frame indexed by a tz-aware UTC DatetimeIndex, carrying the OHLCV
    columns (lower-cased) and every ``x_*`` series found, with the export's title
    decoration stripped.
    """
    raw = pd.read_csv(path)

    time_column = next(
        (c for c in raw.columns if str(c).strip().lower() in {"time", "date", "datetime"}),
        raw.columns[0],
    )
    index = pd.to_datetime(raw[time_column], utc=True, format="mixed")

    renamed: dict[str, str] = {}
    for column in raw.columns:
        if column == time_column:
            continue
        bare = str(column).strip().lower()
        renamed[column] = _normalise(column) if "x_" in bare else bare

    frame = raw.drop(columns=[time_column]).rename(columns=renamed)
    frame.index = pd.DatetimeIndex(index)
    frame = frame[~frame.index.duplicated(keep="first")].sort_index()

    exported = [c for c in frame.columns if str(c).startswith("x_")]
    if not exported:
        raise ValueError(
            f"{path} contains no x_* series. docs/03 section 4 requires the "
            "display.data_window exports; check they were not removed from the Pine, "
            "and that the CSV came from 'Export chart data' rather than a screenshot "
            "of the Data Window."
        )
    return frame


def htf_lattice(weight_tf1: float = 0.6) -> np.ndarray:
    """Every value ``x_htf`` can legally take.

    Three sources, all from ``pine/AZIMUTH.pine:156``
    (``htfUse2 and not na(h2) ? (h1*0.6 + h2*0.4) : nz(h1)``):

    * both horizons present -- ``clip(0.6a + 0.4b)`` for ``a, b`` in the
      four-point vote set, giving 16 points (of which ``+/-1`` and ``+/-1/3``
      coincide with the single-horizon values);
    * HTF2 unavailable -- ``h1`` alone, i.e. the bare vote values;
    * both unavailable -- ``nz(...)`` yields **0**, which is NOT otherwise on the
      lattice: ``0.6a = -0.4b`` has no solution in the vote set. Pine really does
      emit 0 through the warm-up, so excluding it would flag correct output.
    """
    blended = [weight_tf1 * a + (1.0 - weight_tf1) * b for a in _HTF_VOTES for b in _HTF_VOTES]
    return np.unique(np.clip([*blended, *_HTF_VOTES, 0.0], -1.0, 1.0))


def htf_lattice_violations(
    values: FloatSeries, tol: float = 1e-9, weight_tf1: float = 0.6
) -> list[str]:
    """Check ``x_htf`` only takes values it can legally take (finding 11).

    The lattice points are ~0.067 apart at their closest, so an off-lattice value
    cannot come from float noise: it means the series was blended from something
    other than two three-way votes, which is what an alignment or resampling bug
    produces.

    This is the assertion docs/06 section 2's "exact" tolerance was reaching for.
    Strict equality cannot be used because ``0.6*(1/3)`` is not representable in
    binary64.
    """
    lattice = htf_lattice(weight_tf1)
    observed = values.dropna().unique()

    problems: list[str] = []
    if observed.size > lattice.size:
        problems.append(f"{observed.size} distinct values, lattice allows {lattice.size}")
    off = [v for v in observed if np.min(np.abs(lattice - v)) > tol]
    if off:
        shown = ", ".join(f"{v:.12g}" for v in sorted(off)[:5])
        problems.append(f"{len(off)} off-lattice value(s): {shown}")
    return problems


def compare(
    pine: pd.DataFrame,
    python: pd.DataFrame,
    tol: float | None = None,
    burn_in: int = BURN_IN_BARS,
) -> ParityReport:
    """Compare every ``x_*`` series present in both frames, after the burn-in.

    Args:
        tol: Override every per-series tolerance with a single value. ``None``
            uses :data:`TOLERANCES`, which is what ``docs/06`` section 2
            specifies and what the gate should normally run at.
    """
    common = pine.index.intersection(python.index)
    if len(common) <= burn_in:
        raise ValueError(
            f"only {len(common)} overlapping bars, but the burn-in discards {burn_in}. "
            "Export a longer range: docs/07 section 4 wants ~1,000+ bars for the "
            "233-period EMA to be meaningful at all."
        )
    usable = pd.DatetimeIndex(common[burn_in:])

    results: list[ParityResult] = []
    missing: list[str] = []

    for name, default_tol in TOLERANCES.items():
        if name not in pine.columns:
            missing.append(name)
            continue
        if name not in python.columns:
            missing.append(name)
            continue

        tolerance = default_tol if tol is None else tol
        left = pd.to_numeric(pine.loc[usable, name], errors="coerce")
        right = pd.to_numeric(python.loc[usable, name], errors="coerce")

        both = left.notna() & right.notna()
        detail = ""

        if not both.any():
            results.append(ParityResult(name, tolerance, float("nan"), 0, False, "no overlap"))
            continue

        diff = (left[both] - right[both]).abs()
        max_diff = float(diff.max())
        passed = max_diff <= tolerance

        # NaN patterns must agree too: a value present on one side and absent on
        # the other is a warm-up misalignment, which max|delta| would hide.
        nan_mismatch = int((left.isna() != right.isna()).sum())
        if nan_mismatch:
            passed = False
            detail = f"{nan_mismatch} bar(s) na on one side only"

        if name == "x_htf":
            violations: list[str] = []
            # Both sides: an off-lattice value in the EXPORT means the fixture is
            # wrong, which is worth saying rather than blaming our side.
            for label, series in (("pine", left), ("python", right)):
                for problem in htf_lattice_violations(series, tol=1e-9):
                    violations.append(f"{label}: {problem}")
                # 0.0 is legal (Pine's nz() during warm-up), so the lattice check
                # alone cannot catch an HTF series that never seeded. After 283
                # bars it should have: an all-zero x_htf means the resample
                # produced too few HTF bars for the EMA, and the highest-weighted
                # component is silently contributing nothing.
                if both.any() and (series[both].abs() < 1e-12).all():
                    violations.append(
                        f"{label}: identically zero after the burn-in -- HTF never "
                        "seeded (too few HTF bars for htf.ema_length?)"
                    )
            if violations:
                passed = False
                detail = "; ".join([detail, *violations]) if detail else "; ".join(violations)

        results.append(ParityResult(name, tolerance, max_diff, int(both.sum()), passed, detail))

    # Signal bar indices: set equality of trigger timestamps (docs/06 section 2).
    if "x_state" in pine.columns and "x_state" in python.columns:
        results.append(_compare_signal_bars(pine, python, usable))

    return ParityReport(results, len(common), len(usable), missing)


def _compare_signal_bars(
    pine: pd.DataFrame, python: pd.DataFrame, usable: pd.DatetimeIndex
) -> ParityResult:
    """Set equality of the bars on which the state changes.

    docs/06 section 2 asks for the long/short trigger timestamps. Derived from
    ``x_state`` rather than a separate export, since a state change IS a trigger
    and this way the check needs nothing extra from the Pine side.
    """
    left = pd.to_numeric(pine.loc[usable, "x_state"], errors="coerce")
    right = pd.to_numeric(python.loc[usable, "x_state"], errors="coerce")

    left_changes = set(usable[left.diff().fillna(0.0) != 0.0])
    right_changes = set(usable[right.diff().fillna(0.0) != 0.0])

    only_pine = left_changes - right_changes
    only_python = right_changes - left_changes
    passed = not only_pine and not only_python

    detail = ""
    if not passed:
        parts = []
        if only_pine:
            parts.append(f"{len(only_pine)} only in Pine (e.g. {sorted(only_pine)[0]})")
        if only_python:
            parts.append(f"{len(only_python)} only in Python (e.g. {sorted(only_python)[0]})")
        detail = "; ".join(parts)

    return ParityResult(
        "signal_bars",
        0.0,
        0.0 if passed else float(len(only_pine) + len(only_python)),
        len(left_changes),
        passed,
        detail,
    )


def run_parity(
    pine_csv: str | Path,
    config: AzimuthConfig,
    tol: float | None = None,
    burn_in: int = BURN_IN_BARS,
) -> ParityReport:
    """Recompute the core from the fixture's own OHLCV and compare against Pine.

    Recomputing from the fixture rather than re-fetching is deliberate: a vendor
    discrepancy between TradingView's bars and yfinance's would surface as a
    parity failure and send the reader hunting through indicator code for a bug
    that is actually in the data.

    Correlation references come from the fixture's ``x_ref*`` columns (finding
    19). Without them, ``x_corr`` cannot be recomputed and is reported as missing
    rather than silently compared against a zero series.
    """
    pine = load_pine_export(pine_csv)

    required = {"open", "high", "low", "close"}
    if not required.issubset(pine.columns):
        raise ValueError(
            f"{pine_csv} is missing OHLC columns {sorted(required - set(pine.columns))}. "
            "The parity harness recomputes from the fixture's own bars."
        )

    ohlcv = pine[["open", "high", "low", "close"]].astype(float)
    ohlcv["volume"] = pine["volume"].astype(float) if "volume" in pine.columns else 1.0

    refs: dict[str, FloatSeries] = {}
    enabled = [r for r in config.corr.references if r.enabled]
    for index, reference in enumerate(enabled, start=1):
        column = f"x_ref{index}"
        if column in pine.columns:
            refs[reference.symbol] = pd.to_numeric(pine[column], errors="coerce")

    python = compute_frame(ohlcv, config, refs=refs or None)
    return compare(pine, python, tol=tol, burn_in=burn_in)
