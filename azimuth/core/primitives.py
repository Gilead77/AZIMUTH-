"""Pine-exact indicator primitives.

Implements the ``ta.*`` equivalents AZIMUTH needs, matching TradingView's
semantics bar for bar. ``docs/06_PARITY_TESTS.md`` section 3 enumerates the ways
naive pandas implementations diverge; every one is handled here and pinned by a
named regression test.

``pandas_ta`` and TA-Lib are BANNED (CLAUDE.md rule 6, ``docs/04`` section 2).
Their EMA/RSI seeding differs from Pine's and would break parity silently --
silently being the whole problem, since a seeding error decays over hundreds of
bars rather than failing loudly.

Two conventions in this module are DISPUTED between ``docs/06`` section 3 and
TradingView's own reference. Both sit behind a single module-level constant so
the committed Pine fixture can settle them with a one-line change:

* :data:`PCTRANK_STRICT` -- ``docs/06`` says *strictly less than*; TradingView's
  reference says *less than or equal*. (docs/11_FINDINGS.md finding 12.)
* :data:`PIVOT_STRICT_BOTH` -- whether a pivot must beat, or merely match, the
  bars on each side. (docs/11_FINDINGS.md finding 18.)

Everything here is CAUSAL: a value at bar *t* depends only on bars <= *t*. That
is enforced by ``tests/test_lookahead.py``, which is the contract this module was
written against.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from azimuth.core._types import BoolSeries, FloatSeries

__all__ = [
    "EPS",
    "PCTRANK_STRICT",
    "PIVOT_STRICT_BOTH",
    "atr",
    "change",
    "correlation",
    "crossover",
    "crossunder",
    "dmi",
    "ema",
    "fixnan",
    "percentrank",
    "pivot_high",
    "pivot_low",
    "rma",
    "rolling_sum",
    "rsi",
    "sma",
    "stdev",
    "true_range",
    "valuewhen",
]

PCTRANK_STRICT = True
"""Tie-handling for :func:`percentrank`.

``True`` counts prior values *strictly less than* the current one, per
``docs/06_PARITY_TESTS.md`` section 3, which is authoritative for this project.
TradingView's own reference for ``ta.percentrank`` says "less than or equal",
so the two disagree (docs/11_FINDINGS.md finding 12). The fixture decides:
compare ``x_bwpct`` under both settings and keep whichever matches at 1e-6.
"""

PIVOT_STRICT_BOTH = True
"""Comparison used by :func:`pivot_high` / :func:`pivot_low` on both flanks.

``True`` requires the pivot to strictly beat every bar within ``left`` and
``right``. Pine's exact tie-handling for ``ta.pivothigh`` is not pinned down by
the docs, and it only matters on exactly-flat tops and bottoms
(docs/11_FINDINGS.md finding 18). The fixture decides.

The CONFIRMATION LAG is not in question and is not configurable: the value is
always stamped ``right`` bars after the pivot bar. That lag is reproduced
deliberately (``docs/01`` section 3.2) -- lagged is not the same as repainting,
and removing it would be lookahead.
"""

EPS = 1e-10
"""Division guard used by the component modules.

Matches ``math.max(x, 1e-10)`` throughout ``pine/AZIMUTH.pine`` -- ``docs/03``
section 7 item 7: "every denominator uses ``math.max(x, 1e-10)``". Exported from
here so the two cores cannot drift on the guard value; guarding at a different
epsilon than Pine is a parity failure that only shows up on degenerate bars.

Not applied inside the primitives themselves: :func:`rsi` and :func:`dmi`
deliberately let division propagate the way Pine's does (inf, or na), because
clamping there would invent a value where Pine reports none.
"""


# ── helpers ─────────────────────────────────────────────────────────────────────


def _require_length(length: int, minimum: int = 1) -> None:
    if length < minimum:
        raise ValueError(f"length must be >= {minimum}, got {length}")


def _pine_smooth(src: FloatSeries, length: int, alpha: float) -> FloatSeries:
    """Recursive smoother with Pine's SMA seeding.

    THE trap in ``docs/06_PARITY_TESTS.md`` section 3. Pine seeds both ``ta.ema``
    and ``ta.rma`` with the SMA of the first ``length`` observations, then applies
    ``out[i] = alpha*src[i] + (1-alpha)*out[i-1]``.

    ``pandas.ewm(adjust=False)`` instead seeds with the FIRST OBSERVATION, which
    puts the whole series on a different trajectory. The error decays at
    ``(1-alpha)^n`` -- for a 233-period EMA that is still visible hundreds of bars
    later, far beyond any burn-in, and it never announces itself.

    Leading NaNs are skipped, so ``rma`` seeds from the first real observation.
    That matters for :func:`rsi`, whose gain/loss series is NaN at bar 0 because
    ``src[1]`` does not exist -- Pine seeds RSI from bars 1..length, not 0..length-1.
    """
    _require_length(length)
    values = src.to_numpy(dtype=float, copy=False)
    n = values.size
    out = np.full(n, np.nan, dtype=float)

    valid = ~np.isnan(values)
    if not valid.any():
        return pd.Series(out, index=src.index, name=src.name)

    first = int(np.argmax(valid))
    if not valid[first:].all():
        # Interior NaNs would make the recursion ill-defined: Pine propagates na
        # from that point on, which is never what a caller wants. docs/04 section 5
        # validates OHLC has no NaNs, so this indicates a bug upstream.
        bad = first + int(np.argmax(~valid[first:]))
        raise ValueError(
            f"interior NaN at index {bad}: recursive smoothing is undefined across gaps. "
            "docs/04_SPEC_PYTHON_CLI.md section 5 requires OHLC with no NaNs."
        )

    seed_end = first + length  # exclusive
    if seed_end > n:
        return pd.Series(out, index=src.index, name=src.name)

    out[seed_end - 1] = values[first:seed_end].mean()
    for i in range(seed_end, n):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]

    return pd.Series(out, index=src.index, name=src.name)


# ── moving averages ─────────────────────────────────────────────────────────────


def sma(src: FloatSeries, length: int) -> FloatSeries:
    """Simple moving average. NaN until ``length`` observations exist."""
    _require_length(length)
    return src.rolling(length).mean()


def ema(src: FloatSeries, length: int) -> FloatSeries:
    """``ta.ema``: SMA-seeded, ``alpha = 2/(length+1)``.

    Do NOT substitute ``src.ewm(span=length, adjust=False).mean()`` -- see
    :func:`_pine_smooth`. ``tests/test_ema_seeding.py`` pins the difference.
    """
    _require_length(length)
    return _pine_smooth(src, length, alpha=2.0 / (length + 1.0))


def rma(src: FloatSeries, length: int) -> FloatSeries:
    """``ta.rma``: Wilder's smoother, SMA-seeded, ``alpha = 1/length``.

    Used inside :func:`rsi`, :func:`atr` and :func:`dmi`. Wilder smoothing
    throughout is what most library ADX implementations get wrong
    (``docs/06`` section 3).
    """
    _require_length(length)
    return _pine_smooth(src, length, alpha=1.0 / length)


# ── dispersion ──────────────────────────────────────────────────────────────────


def stdev(src: FloatSeries, length: int) -> FloatSeries:
    """``ta.stdev``: POPULATION standard deviation, ``ddof=0``.

    ``pandas.rolling().std()`` defaults to ``ddof=1`` (``docs/06`` section 3).
    For the 20-period Bollinger basis that is a factor of ``sqrt(20/19)`` ~= 1.026
    on the band width -- small enough to look plausible on a chart and large
    enough to destroy parity at 1e-6. ``tests/test_stdev_ddof.py`` pins it.
    """
    _require_length(length, minimum=2)
    return src.rolling(length).std(ddof=0)


# ── momentum ────────────────────────────────────────────────────────────────────


def change(src: FloatSeries, length: int = 1) -> FloatSeries:
    """``ta.change``: ``src - src[length]``. NaN for the first ``length`` bars."""
    _require_length(length)
    return src.diff(length)


def rolling_sum(src: FloatSeries, length: int) -> FloatSeries:
    """``math.sum``: rolling sum over ``length`` bars."""
    _require_length(length)
    return src.rolling(length).sum()


def rsi(src: FloatSeries, length: int) -> FloatSeries:
    """``ta.rsi``, built on :func:`rma` exactly as Pine builds it::

        u  = max(src - src[1], 0)
        d  = max(src[1] - src, 0)
        rs = rma(u, length) / rma(d, length)
        rsi = 100 - 100 / (1 + rs)

    Division behaviour is left to propagate naturally because that is what Pine
    does: an all-gains window gives ``rs = inf`` and therefore ``rsi = 100``,
    while a perfectly flat window gives ``0/0 = NaN`` and therefore ``NaN`` --
    NOT 50, which is what several libraries return and which would silently
    break parity on illiquid bars.
    """
    _require_length(length, minimum=2)
    delta = src.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = rma(gain, length)
    avg_loss = rma(loss, length)

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        out = 100.0 - 100.0 / (1.0 + rs)

    return pd.Series(np.asarray(out, dtype=float), index=src.index, name=src.name)


# ── volatility ──────────────────────────────────────────────────────────────────


def true_range(
    high: FloatSeries, low: FloatSeries, close: FloatSeries, handle_na: bool = True
) -> FloatSeries:
    """``ta.tr``: ``max(high-low, |high-close[1]|, |low-close[1]|)``.

    Args:
        handle_na: Pine's ``ta.tr(true)`` semantics -- on the first bar, where
            ``close[1]`` does not exist, fall back to ``high - low``. ``ta.atr``
            uses this. ``ta.dmi`` uses the bare ``ta.tr``, i.e. ``handle_na=False``,
            which is NaN on the first bar. The distinction only moves the seed by
            one bar and is invisible after burn-in, but it is free to get right.
    """
    prev_close = close.shift(1)
    hl = high - low
    tr = np.maximum(np.maximum(hl, (high - prev_close).abs()), (low - prev_close).abs())
    out = pd.Series(np.asarray(tr, dtype=float), index=close.index, name="tr")
    if handle_na:
        out = out.where(prev_close.notna(), hl)
    return out


def atr(high: FloatSeries, low: FloatSeries, close: FloatSeries, length: int) -> FloatSeries:
    """``ta.atr``: ``rma(tr, length)`` with ``ta.tr(true)``.

    Note for parity debugging: ``x_ribbon`` divides the EMA-34 slope by this
    (``pine/AZIMUTH.pine:123``), so a ribbon parity failure at 1e-6 is more often
    an ATR/RMA seeding bug than an EMA bug. Check this first.
    """
    _require_length(length)
    return rma(true_range(high, low, close, handle_na=True), length)


# ── ranking ─────────────────────────────────────────────────────────────────────


def percentrank(src: FloatSeries, length: int, strict: bool | None = None) -> FloatSeries:
    """``ta.percentrank``: rank of the current value against the PRIOR ``length``.

    Two things ``pandas.rank(pct=True)`` gets wrong and which ``docs/06``
    section 3 warns about explicitly:

    * the current bar is EXCLUDED from its own comparison window;
    * the count is of values *strictly less than* the current one, not a
      tie-averaged rank.

    Returns NaN for the first ``length`` bars, matching Pine.

    Args:
        strict: Override :data:`PCTRANK_STRICT` for one call. Used by
            ``tests/test_percentrank_convention.py`` to demonstrate both
            readings while the fixture is outstanding (finding 12).
    """
    _require_length(length)
    use_strict = PCTRANK_STRICT if strict is None else strict

    values = src.to_numpy(dtype=float, copy=False)
    n = values.size
    out = np.full(n, np.nan, dtype=float)

    for i in range(length, n):
        current = values[i]
        window = values[i - length : i]
        if np.isnan(current) or np.isnan(window).any():
            continue
        count = np.count_nonzero(window < current if use_strict else window <= current)
        out[i] = 100.0 * count / length

    return pd.Series(out, index=src.index, name=src.name)


def correlation(x: FloatSeries, y: FloatSeries, length: int) -> FloatSeries:
    """``ta.correlation``: rolling Pearson correlation over ``length`` bars.

    ``docs/06`` section 3 records this one as matching pandas directly.

    Caveat that is NOT a parity issue but decides whether the number means
    anything -- docs/11_FINDINGS.md finding 3: when the two series trade on
    different calendars, the forward-filled one contributes structural zero
    returns and the correlation rests on far fewer real observations than
    ``length`` suggests. Pine and pandas agree on the same near-meaningless value.
    """
    _require_length(length, minimum=2)
    return x.rolling(length).corr(y)


# ── pivots ──────────────────────────────────────────────────────────────────────


def _pivot(src: FloatSeries, left: int, right: int, find_high: bool) -> FloatSeries:
    """Shared pivot machinery. See :func:`pivot_high` for the contract."""
    _require_length(left)
    _require_length(right)

    values = src.to_numpy(dtype=float, copy=False)
    n = values.size
    out = np.full(n, np.nan, dtype=float)

    for p in range(left, n - right):
        candidate = values[p]
        if np.isnan(candidate):
            continue

        flanks = np.concatenate((values[p - left : p], values[p + 1 : p + right + 1]))
        if np.isnan(flanks).any():
            continue

        if find_high:
            ok = (
                bool((flanks < candidate).all())
                if PIVOT_STRICT_BOTH
                else bool((flanks <= candidate).all())
            )
        else:
            ok = (
                bool((flanks > candidate).all())
                if PIVOT_STRICT_BOTH
                else bool((flanks >= candidate).all())
            )

        if ok:
            # Stamped at the CONFIRMATION bar, `right` bars after the pivot.
            # This is what makes the function causal: the value at index p+right
            # depends only on bars p-left .. p+right, all of which are <= p+right.
            out[p + right] = candidate

    return pd.Series(out, index=src.index, name=src.name)


def pivot_high(src: FloatSeries, left: int, right: int) -> FloatSeries:
    """``ta.pivothigh``: the pivot's value, stamped ``right`` bars late.

    The returned series is NaN except at confirmation bars. To recover the bar the
    pivot actually occurred on, read back ``right`` bars -- which is exactly what
    ``pine/AZIMUTH.pine:142-145`` does with ``rsi[divLb]`` and ``low[divLb]``.

    THE LAG IS THE POINT. ``docs/03`` section 2: "Pivot-confirmed with ``divLb``
    bars of lag. Lagged != repainting. Do not 'improve' this by reducing legs to
    1." A centred implementation that stamps the value at the pivot bar reads
    ``right`` bars into the future and is caught by
    ``tests/test_lookahead.py::test_pivot_confirmation_is_lagged_not_centred``.
    """
    return _pivot(src, left, right, find_high=True)


def pivot_low(src: FloatSeries, left: int, right: int) -> FloatSeries:
    """``ta.pivotlow``. Mirror of :func:`pivot_high`; same confirmation lag."""
    return _pivot(src, left, right, find_high=False)


# ── directional movement ────────────────────────────────────────────────────────


def dmi(
    high: FloatSeries,
    low: FloatSeries,
    close: FloatSeries,
    di_length: int,
    adx_smoothing: int,
) -> tuple[FloatSeries, FloatSeries, FloatSeries]:
    """``ta.dmi``: returns ``(+DI, -DI, ADX)``.

    Wilder smoothing throughout -- ``docs/06`` section 3 flags that most library
    ADX implementations differ here, typically by using an EMA or a plain SMA for
    one of the three smoothing steps.

    Transcribed from TradingView's reference implementation::

        up       = change(high)
        down     = -change(low)
        plusDM   = up > down and up > 0     ? up   : 0
        minusDM  = down > up and down > 0   ? down : 0
        trur     = rma(tr, di_length)
        plus     = fixnan(100 * rma(plusDM, di_length) / trur)
        minus    = fixnan(100 * rma(minusDM, di_length) / trur)
        adx      = 100 * rma(|plus - minus| / (sum == 0 ? 1 : sum), adx_smoothing)

    Note the ADX line: the ratio is smoothed and THEN scaled by 100. Smoothing
    ``100 * ratio`` instead is arithmetically identical, but computing
    ``100 * |plus-minus| / sum`` first and smoothing that is a different and
    commonly seen mistake when the zero-guard is applied in the wrong place.

    ``ta.dmi`` returns a 3-tuple -- unpack all three (``docs/03`` section 7 item 2).
    """
    _require_length(di_length, minimum=2)
    _require_length(adx_smoothing, minimum=2)

    up = change(high)
    down = -change(low)

    plus_dm = pd.Series(
        np.where((up > down) & (up > 0.0), up, 0.0), index=high.index, dtype=float
    ).where(up.notna())
    minus_dm = pd.Series(
        np.where((down > up) & (down > 0.0), down, 0.0), index=low.index, dtype=float
    ).where(down.notna())

    # Bare `ta.tr` (handle_na=False) inside dmi, per the reference implementation.
    trur = rma(true_range(high, low, close, handle_na=False), di_length)

    with np.errstate(divide="ignore", invalid="ignore"):
        plus = fixnan(100.0 * rma(plus_dm, di_length) / trur)
        minus = fixnan(100.0 * rma(minus_dm, di_length) / trur)

        total = plus + minus
        ratio = (plus - minus).abs() / total.where(total != 0.0, 1.0)
        adx = 100.0 * rma(ratio, adx_smoothing)

    return plus, minus, adx


# ── state helpers ───────────────────────────────────────────────────────────────


def fixnan(src: FloatSeries) -> FloatSeries:
    """``fixnan``: replace NaN with the last non-NaN value.

    FORWARD fill only. Leading NaNs stay NaN -- there is no earlier value to carry,
    and back-filling from a later one would be lookahead wearing the costume of a
    convenience. Pinned by
    ``tests/test_lookahead.py::test_state_dependent_primitives_do_not_backfill``.
    """
    return src.ffill()


def crossover(a: FloatSeries, b: FloatSeries) -> BoolSeries:
    """``ta.crossover``: ``a`` was at or below ``b`` and is now above.

    Drives entries in ``docs/02`` section 3. NaN on either side yields False,
    matching Pine, so the burn-in region cannot fire a signal.
    """
    crossed = (a > b) & (a.shift(1) <= b.shift(1))
    return crossed.fillna(value=False).astype(bool)


def crossunder(a: FloatSeries, b: FloatSeries) -> BoolSeries:
    """``ta.crossunder``: ``a`` was at or above ``b`` and is now below."""
    crossed = (a < b) & (a.shift(1) >= b.shift(1))
    return crossed.fillna(value=False).astype(bool)


def valuewhen(condition: BoolSeries, source: FloatSeries, occurrence: int) -> FloatSeries:
    """``ta.valuewhen``: ``source`` when ``condition`` was last true.

    ``occurrence`` counts back from the present: 0 is the most recent true bar
    (including the current one), 1 the one before it. ``pine/AZIMUTH.pine:142-145``
    uses occurrences 0 and 1 to compare consecutive pivots for divergence.

    ``docs/03`` section 7 item 6 notes Pine requires a ``simple int`` here -- the
    occurrence cannot vary bar to bar, which is why this takes a plain ``int``.
    """
    if occurrence < 0:
        raise ValueError(f"occurrence must be >= 0, got {occurrence}")

    flags = condition.to_numpy(dtype=bool, copy=False)
    values = source.to_numpy(dtype=float, copy=False)
    n = flags.size
    out = np.full(n, np.nan, dtype=float)

    true_positions = np.flatnonzero(flags)
    if true_positions.size:
        # Number of true bars at or before each index, minus one, gives the
        # position of the most recent true bar within `true_positions`.
        most_recent = np.searchsorted(true_positions, np.arange(n), side="right") - 1
        target = most_recent - occurrence
        found = target >= 0
        out[found] = values[true_positions[target[found]]]

    return pd.Series(out, index=source.index, name=source.name)
