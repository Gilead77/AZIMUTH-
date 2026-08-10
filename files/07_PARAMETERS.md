# 07 — Parameter Reference

## 1. Canonical naming

| Pine input | YAML key | Default | Sweep range | Rationale |
|---|---|---|---|---|
| `l1..l8` | `ribbon.lengths` | 8,13,21,34,55,89,144,233 | 3 preset sets only | Fibonacci is convention, not magic. Sweeping 8 lengths freely is a guaranteed overfit — restrict to whole-set presets |
| `ribSlopeLb` | `ribbon.slope_lookback` | 5 | 3–10 | |
| `ribCompLb` | `ribbon.compress_lookback` | 200 | 100–300 | |
| `ribCompTh` | `ribbon.compress_pctile` | 20 | 10–30 | |
| `bbLen` | `bollinger.length` | 20 | 14–30 | |
| `bbMult` | `bollinger.mult` | 2.0 | 1.5–2.5 | |
| `bbLb` | `bollinger.bw_lookback` | 200 | 100–300 | |
| `bbSqzTh` | `bollinger.squeeze_pctile` | 20 | 10–30 | |
| `rsiLen` | `rsi.length` | 14 | 9–21 | |
| `rsiSpan` | `rsi.span` | 25 | 15–35 | Distance from 50 mapping to full score |
| `divLb` | `rsi.div_legs` | 5 | 3–8 | Higher = fewer, cleaner, later |
| `divBonus` | `rsi.div_bonus` | 0.35 | 0.0–0.5 | Include 0.0 to test whether divergence adds anything |
| `htf1` | `htf.tf1` | 240 | ~4× chart TF | |
| `htf2` | `htf.tf2` | 1D | ~24× chart TF | |
| `htfEmaLen` | `htf.ema_length` | 50 | 20–100 | |
| `htfConfirm` | `htf.confirmed_only` | true | **fixed true** | Never sweep. False = lookahead |
| `corrLen` | `corr.length` | 60 | 30–120 | |
| `corrMin` | `corr.min_abs_rho` | 0.30 | 0.2–0.5 | |
| `corrRefEma` | `corr.ref_ema` | 50 | 20–100 | |
| `erLen` / `erTh` | `regime.er_length` / `er_threshold` | 20 / 0.30 | 10–30 / 0.2–0.4 | |
| `adxLen` / `adxTh` | `regime.adx_length` / `adx_threshold` | 14 / 20 | 10–20 / 15–30 | |
| `regimeMode` | `regime.mode` | adaptive | 3 discrete modes | Test as separate hypotheses |
| `wRib..wCorr` | `weights.*` | 1.0/0.8/0.8/1.2/0.5 | 0.0–1.5 step 0.25 | **Equal weights is a mandatory baseline** |
| `enterTh` | `signal.enter` | 45 | 30–65 | |
| `exitTh` | `signal.exit` | 15 | 0–30, must be < enter | |
| `cooldown` | `signal.cooldown_bars` | 8 | 0–20 | |
| `atrStop` | `risk.atr_stop_mult` | 2.0 | 1.0–3.5 | |
| `rrTarget` | `risk.rr_target` | 2.0 | 1.0–4.0 | |

## 2. Combinatorial warning ⚠️

A full grid over the ranges above is roughly **10^13 configurations**. Do not
attempt it. Mandated approach:

1. **Stage 1 — structure.** Fix all weights equal, fix thresholds at default.
   Sweep only regime mode and the three preset ribbon sets. 9 configurations.
2. **Stage 2 — signal.** With Stage 1's winner fixed, sweep `enterTh`, `exitTh`,
   `cooldown`. ~200 configurations.
3. **Stage 3 — risk.** Sweep `atrStop`, `rrTarget`. ~50 configurations.
4. **Stage 4 — weights.** Coarse random search, 500 draws, Latin hypercube.

Cumulative `N ≈ 760`. Record it. Feed it to the Deflated Sharpe calculation.
**Every re-run adds to N. Keep a running total in `runs/N_trials.txt`.**

## 3. Timeframe guidance

| Chart TF | HTF1 | HTF2 | Notes |
|---|---|---|---|
| 15m | 1H | 4H | High trade count; costs dominate — check break-even early |
| 1H | 4H | 1D | Probably the sweet spot for this design |
| 4H | 1D | 1W | Fewest trades; may fail criterion 10 (n ≥ 100) |
| 1D | 1W | 1M | 233-EMA needs ~5 years of history minimum |

## 4. Instrument suitability

Best fit: liquid, trending, with genuine cross-asset relationships —
major FX, index futures, large-cap crypto, gold.

Poor fit: low-liquidity alts (correlation refs meaningless, costs enormous),
single equities around earnings (gap risk breaks ATR stops), anything where the
233-EMA has under ~1,000 bars of history.

## 5. Correlation reference selection 🔗

**Choose by causal story, then verify stability. Never choose by highest ρ.**

| Instrument | Sensible refs | Why |
|---|---|---|
| Gold | DXY, US10Y real yield, SPX | Dollar and real-rate mechanics are the actual drivers |
| BTC | SPX/NDX, DXY, ETH | Risk-appetite proxy + dollar liquidity |
| GBPUSD | DXY, UK–US 2Y spread, FTSE | Rate differential is the textbook driver |
| SPX | VIX, DXY, US10Y | |

Then run `azimuth validate --check-rho-stability`: split the sample in halves and
report ρ in each. **If the sign flips between halves, drop that reference.**
Unstable correlations actively degrade the score — they contribute confident
votes in the wrong direction.
