# 04 — Python CLI Specification

## 1. Purpose

The CLI is **not** a trading bot. It is the instrument that decides whether
AZIMUTH is real. Secondary use: generating live signal tables offline.

## 2. Stack

| Concern | Choice |
|---|---|
| Python | 3.11+ |
| CLI | `typer` + `rich` |
| Data | `pandas`, `numpy`, `pyarrow` |
| Sources | `yfinance` (equities/FX/indices), `ccxt` (crypto), local CSV |
| Stats | `scipy`, `statsmodels` |
| Plots | `plotly` (interactive HTML report) |
| Config | `pydantic-settings` + YAML |
| Tests | `pytest`, `hypothesis` |
| Packaging | `uv` + `pyproject.toml` |

No TA-Lib dependency — indicator maths is implemented in-repo so it can be made
bit-comparable to Pine. `pandas_ta` is explicitly **banned**: its EMA/RSI seeding
differs from Pine's and will break parity.

## 3. Layout

```
azimuth/
├── cli.py                 # typer app
├── config/
│   ├── schema.py          # pydantic models
│   └── default.yaml
├── data/
│   ├── loaders.py         # yfinance / ccxt / csv → canonical OHLCV frame
│   ├── resample.py        # HTF construction, right-closed right-labelled
│   └── cache.py           # parquet, keyed by (symbol, tf, start, end)
├── core/
│   ├── primitives.py      # ema, rsi, stdev, atr, percentrank, correlation, dmi
│   ├── ribbon.py
│   ├── bollinger.py
│   ├── rsi_mod.py
│   ├── htf.py
│   ├── correlation.py
│   ├── regime.py
│   ├── score.py           # composite
│   └── signals.py         # state machine (must mirror 02_SPEC_SCORING §3)
├── backtest/
│   ├── engine.py          # event-ordered, next-bar-open fills
│   ├── costs.py           # spread / commission / slippage models
│   └── metrics.py         # CAGR, Sharpe, Sortino, MaxDD, Calmar, PF, expectancy
├── validate/
│   ├── walkforward.py     # purged + embargoed anchored & rolling
│   ├── permutation.py     # bar/return permutation null
│   ├── spa.py             # White's Reality Check, Hansen SPA
│   ├── dsr.py             # deflated & probabilistic Sharpe
│   ├── benchmarks.py      # buy&hold, random-entry matched
│   └── parity.py          # vs Pine CSV export
├── report/
│   ├── html.py            # single self-contained HTML
│   └── plots.py
└── alerts/
    └── watch.py           # poll → evaluate → emit (webhook/stdout/ntfy)
```

## 4. Commands

```bash
azimuth fetch    --symbol BTC-USD --tf 4h --start 2018-01-01 [--source ccxt]
azimuth signals  --symbol BTC-USD --tf 4h [--last 20] [--json]
azimuth backtest --symbol BTC-USD --tf 4h --config config/default.yaml
azimuth sweep    --grid config/grid.yaml --out runs/sweep_001 --workers 8
azimuth validate --run runs/sweep_001 --preregistration docs/09_PREREGISTRATION.md
azimuth ablate   --symbol BTC-USD --tf 4h          # zero each weight in turn
azimuth parity   --pine exports/AZIMUTH_BTCUSD_4h.csv --tol 1e-6
azimuth report   --run runs/sweep_001 --out reports/azimuth_001.html
azimuth watch    --symbols BTC-USD,ETH-USD --tf 4h --webhook $WEBHOOK_URL
```

### Global flags
`--config`, `--cache-dir`, `--seed`, `--log-level`, `--no-cache`

### `validate` guard rail 🔒
`azimuth validate` **must refuse to run** unless the pre-registration file exists,
is filled in, and its SHA-256 is recorded in the run manifest *before* the sweep
was executed. Implement as a hard error, not a warning. The whole point is that
the hypothesis cannot be edited after seeing results.

## 5. Canonical data frame

Every loader returns:
```
index: pd.DatetimeIndex, tz-aware UTC, monotonic, no duplicates
cols : open, high, low, close, volume   (float64)
attrs: symbol, timeframe, source, fetched_at
```
Validation on load: no NaNs in OHLC, `high ≥ max(open,close)`, `low ≤ min(open,close)`,
gap report emitted to stderr.

## 6. HTF construction (parity-critical)

Pine's HTF bars are **right-closed, right-labelled**, and a value is only
available *after* the HTF bar closes. Python must replicate:

```python
htf = df.resample(rule, label="right", closed="right").agg(OHLCV_AGG)
htf_score = compute_htf_score(htf).shift(1)          # confirmed bar only
aligned = htf_score.reindex(df.index, method="ffill")
```

The `.shift(1)` is the equivalent of returning `s[1]` inside `request.security`.
Omitting it produces lookahead and is the most likely source of a fake edge.

## 7. Backtest engine rules

- Signals computed on close of bar *t* → order filled at open of bar *t+1*.
- Stop and target checked intrabar on *t+1* onwards. When both are touched in the
  same bar, assume the **stop** filled first (conservative; log the ambiguity count).
- Costs: `total = spread_bps/2 + commission_bps + slippage_bps` per side.
- Position sizing: fixed fractional by default; `--vol-target` optional.
- Output: trade ledger parquet + equity series + metrics JSON.

## 8. Determinism

Every run writes `manifest.json`: git SHA, config hash, data hash, seed, package
versions, wall-clock. Two runs with the same manifest must produce byte-identical
metrics. Add a CI test that asserts this.
