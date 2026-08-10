# 06 — Pine ↔ Python Parity Harness

If Pine and Python disagree, every validation result is worthless — you would be
validating a different system from the one that trades. Parity is a gate, not a
nice-to-have.

## 1. Procedure

1. Load `AZIMUTH.pine` on a chart. Set a fixed symbol/timeframe/date range.
2. Chart menu → **Export chart data** → CSV. This includes all `x_*` plots.
3. `azimuth parity --pine exports/<file>.csv --tol 1e-6`

## 2. Assertions

| Series | Tolerance | Notes |
|---|---|---|
| `x_ribbon` | 1e-6 | EMA seeding must match (see §3) |
| `x_bb`, `x_pctb`, `x_bwpct` | 1e-6 | `stdev` is population (`ddof=0`) in Pine |
| `x_rsi` | 1e-5 | RMA seeding differs for first `len` bars — burn-in excluded |
| `x_htf` | exact | Categorical ±1/3 steps; any mismatch = alignment bug |
| `x_corr` | 1e-5 | |
| `x_er`, `x_adx` | 1e-5 | |
| `x_state` | exact | Integer state machine — must match bar-for-bar |
| Signal bar indices | exact | Set equality of long/short trigger timestamps |

Burn-in: discard the first `max(233, 200, 60) + 50 = 283` bars before comparing.

## 3. Known Pine/Python divergences to handle explicitly

| Function | Pine behaviour | Python implementation |
|---|---|---|
| `ta.ema` | Seeded with SMA of first `len` bars, then `α = 2/(len+1)` | `pandas.ewm(span=len, adjust=False)` **after** seeding first value with `SMA(len)`. Plain `ewm(adjust=False)` seeds with the first observation → drift for hundreds of bars |
| `ta.rma` (inside RSI/ATR) | Wilder's: `α = 1/len`, SMA-seeded | `ewm(alpha=1/len, adjust=False)` with SMA seed |
| `ta.stdev` | Population, `ddof=0` | `rolling(len).std(ddof=0)` — pandas defaults to `ddof=1` ⚠️ |
| `ta.percentrank` | % of prior values **strictly less than** current, over `len` **excluding** current | Custom rolling implementation; do not use `rank(pct=True)` |
| `ta.correlation` | Pearson over `len` | `rolling(len).corr()` — matches |
| `ta.pivotlow/high` | Confirmed `legs` bars later, value stamped at pivot bar | Custom; assert the confirmation lag explicitly in a unit test |
| `ta.dmi` | Wilder smoothing throughout | Implement from scratch; `ta.ADX` in other libs commonly differs |
| `na` handling | Propagates | Use `np.nan`, never `0` fill |

## 4. Unit tests (`tests/`)

```
test_primitives.py     # each ta.* equivalent vs hand-computed fixtures
test_ema_seeding.py    # explicit regression test for the SMA-seed issue
test_stdev_ddof.py     # explicit regression test for ddof=0
test_htf_alignment.py  # synthetic data; asserts zero lookahead
test_lookahead.py      # property test: truncating the series at bar t must
                       # never change any value at bars ≤ t   (hypothesis)
test_state_machine.py  # table-driven cases for entry/exit/cooldown/hysteresis
test_parity.py         # runs against committed fixture CSV in tests/fixtures/
```

`test_lookahead.py` is the most important test in the repo. Implement it first.

## 5. CI

GitHub Actions: on every push, run unit tests + parity against the committed
fixture export. Parity failure = red build. Do not merge around it.
