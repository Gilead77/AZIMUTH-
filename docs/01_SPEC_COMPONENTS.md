# 01 — Component Specification

Every component returns a score `s ∈ [-1, +1]`. Positive = long-favourable.
All clipping uses `clip(x) = max(-1, min(1, x))`.

---

## 1. EMA Ribbon 🎀

**Lengths (default):** Fibonacci `[8, 13, 21, 34, 55, 89, 144, 233]`

### 1.1 Stacking score
```
bullPairs = Σ_{i=0..6} [ EMA_i > EMA_{i+1} ]
ribOrder  = (bullPairs / 7) * 2 − 1          ∈ [−1, +1]
```
Perfect bullish fan → `+1`. Perfect bearish fan → `−1`. Tangle → ~`0`.
This is deliberately **ordinal**, not distance-based: it is scale-free and
survives regime changes in volatility.

### 1.2 Slope score
```
ribSlope = clip( (EMA_34 − EMA_34[k]) / (ATR_14 × k) ),  k = ribSlopeLb (5)
```
ATR normalisation makes slope comparable across instruments and timeframes.

### 1.3 Composite
```
ribScore = clip( 0.65 × ribOrder + 0.35 × ribSlope )
```

### 1.4 Compression flag (setup, not direction)
```
ribWidth   = (max(EMAs) − min(EMAs)) / close
ribWidthPc = percentrank(ribWidth, 200)
ribCompress = ribWidthPc < 20
```

---

## 2. Bollinger Bands

```
basis = SMA(close, 20)
σ     = stdev(close, 20)
upper, lower = basis ± 2σ
%B      = (close − lower) / (upper − lower)
bandwidth   = (upper − lower) / basis
bwPct       = percentrank(bandwidth, 200)
bbSqueeze   = bwPct < 20
```

### Regime-dependent polarity ⚠️
This is the single most important design decision in AZIMUTH.

| Regime | Logic | Score |
|---|---|---|
| Trend | Band ride = strength | `clip((%B − 0.5) × 2)` |
| Range | Band tag = exhaustion | `clip((0.5 − %B) × 2)` |

A fixed-polarity Bollinger rule is the classic reason confluence systems fail:
mean-reversion logic applied inside a trend bleeds continuously.

---

## 3. RSI

```
rsi = RSI(close, 14)
```

### 3.1 Base score — regime-dependent, same rationale as BB
| Regime | Score |
|---|---|
| Trend | `clip((rsi − 50) / span)`, span = 25 |
| Range | `clip((50 − rsi) / span)` |

Note the 50-line is the centre, **not** 30/70. In an uptrend RSI oscillates
roughly 40–80 and never reaches 30; an "oversold buy" rule simply never fires
where it would have worked.

### 3.2 Regular divergence bonus
Pivot-based, `divLb = 5` legs each side:
- **Bullish:** price makes a lower low, RSI makes a higher low → `+0.35`
- **Bearish:** price makes a higher high, RSI makes a lower high → `−0.35`

⚠️ Pivots confirm `divLb` bars late. This is **not** repainting (the value never
changes once printed) but it **is** lag. The Python harness must reproduce the
same lag exactly — see `06_PARITY_TESTS.md`.

```
rsiScore = clip( base + bullDivBonus − bearDivBonus )
```

---

## 4. Higher-Timeframe Bias 🕰️

Computed **in the HTF context**, then pulled down. For each HTF:
```
he = EMA(close, 50)          # in HTF
hr = RSI(close, 14)          # in HTF
s  = ( sign(close − he) + sign(he − he[3]) + sign(hr − 50) ) / 3
value = s[1]                 # previous CLOSED HTF bar
```

Two horizons, weighted:
```
htfScore = clip( 0.6 × HTF1 + 0.4 × HTF2 )      # default 4H, 1D
```

**Repaint contract:** `request.security(..., expr[1], lookahead=lookahead_off)`.
Returning `s[1]` from inside the HTF context means the value is fixed from the
moment the HTF bar closes. It costs up to one HTF bar of lag. That cost is
non-negotiable — the alternative silently inflates every backtest.

---

## 5. Cross-Asset Correlation 🔗

Correlation is computed on **log returns**, not prices. Price-level correlation
between two trending series is close to meaningless (spurious regression).

For each reference symbol *j*:
```
r_own = ln(close / close[1])
r_ref = ln(ref  / ref[1])
ρ_j   = correlation(r_own, r_ref, 60)
trend_j = sign( ref − EMA(ref, 50) )
```

### Contribution
```
contrib_j = |ρ_j| ≥ ρ_min ?  ρ_j × trend_j  : 0
corrScore = clip( Σ contrib_j / count(active j) )
```

Read this as: *"the reference is trending up; we are positively correlated with
it; therefore up is favoured — and the strength of that vote scales with ρ."*
Negative ρ flips the vote, which is exactly right for DXY vs. most risk assets.

### Crowding flag (risk, not direction)
```
crowding = mean( |ρ_j| )
```
High crowding = everything is one trade. Feed this to position sizing, not to
the directional score.

### Reference selection
Defaults (`DXY`, `SPX`, `GOLD`) are **placeholders**. Pick references with a
causal story, not the highest historical ρ — the latter is data-snooping and
correlations are famously unstable. See `07_PARAMETERS.md` §5.

---

## 6. Regime Gate 🚦

Two independent estimators, OR-combined:

### Kaufman Efficiency Ratio
```
ER = |close − close[n]| / Σ|close − close[1]|   over n=20      ∈ [0, 1]
```
Directional travel ÷ total travel. `ER > 0.30` → trending.

### ADX
```
[+DI, −DI, ADX] = DMI(14, 14)
ADX > 20 → trending
```

```
trending = (ER > 0.30) OR (ADX > 20)
```

`regimeMode` input can force `Trend only` / `Range only` for ablation testing —
the harness must run all three modes as separate hypotheses, not pick the best.

---

## 7. Suggested additions (implement behind flags, test separately)

These are proposals, each of which must earn its place by improving
out-of-sample performance in the walk-forward — not by looking sensible.

| Addition | Rationale | Flag |
|---|---|---|
| **Relative volume** `vol / SMA(vol,20)` as an entry multiplier | Breakouts on thin volume fail more often | `--use-rvol` |
| **Volatility-targeted sizing** `size ∝ target_vol / realised_vol` | Equalises risk contribution across regimes; usually the single largest Sharpe improvement in any system | `--vol-target` |
| **Session filter** | Kills the dead-hours chop that generates most false signals on intraday FX/crypto | `--sessions` |
| **Crowding haircut** `size × (1 − crowding)` | Cuts exposure when correlation says you only have one position | `--crowding-haircut` |
| **Anchored VWAP distance** | Institutional reference level; adds a genuinely different information axis | `--use-avwap` |
| **Time-based stop** (exit after N bars if not at +1R) | Prevents dead capital; cheap and usually positive | `--time-stop` |
| **Score slope** as a separate gate (`d(score)/dt > 0`) | Distinguishes strengthening from decaying confluence | `--score-slope` |

Explicitly **not** recommended: adding more oscillators. RSI, Stochastic, CCI,
MFI and Williams %R are near-collinear; stacking them multiplies parameters
without adding information, which is the fastest route to an overfit.
