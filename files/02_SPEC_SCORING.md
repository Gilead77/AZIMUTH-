# 02 — Composite Scoring & Signal State Machine

## 1. Composite

```
score = 100 × ( Σ w_i · s_i ) / Σ w_i        ∈ [−100, +100]
```

| Component | Default weight | Why |
|---|---|---|
| HTF bias | 1.2 | Highest weight: trend context dominates single-bar signals empirically |
| Ribbon 🎀 | 1.0 | Primary directional read on the trading timeframe |
| Bollinger | 0.8 | Location/extension, regime-flipped |
| RSI | 0.8 | Momentum, regime-flipped, partially collinear with ribbon |
| Correlation 🔗 | 0.5 | Contextual confirmation; noisiest and least stable |

**Weights are hyperparameters and must be swept, not tuned by eye.**
Include an equal-weight configuration `(1,1,1,1,1)` as a mandatory baseline in
every walk-forward — if the tuned weights don't beat equal weights out of
sample, use equal weights. They usually don't.

## 2. Regime polarity switch

```
trending = ER > 0.30 OR ADX > 20

bbScore  = trending ?  (%B − 0.5)×2   :  (0.5 − %B)×2
rsiScore = trending ? (rsi − 50)/25   :  (50 − rsi)/25
```

Ribbon, HTF and correlation scores are **not** flipped — they are directional
context in both regimes.

## 3. State machine

```
state ∈ {−1 short, 0 flat, +1 long}
```

### Entry
```
longTrig  = state ≤ 0
          ∧ crossover(score, +enterTh)          # 45
          ∧ (bar_index − lastSignalBar ≥ cooldown)   # 8
          ∧ (¬reqTrend  ∨ trending)
          ∧ (¬reqHTF    ∨ htfScore > 0)
```
Short is the mirror image.

### Exit (hysteresis)
```
exitLong  = state = +1 ∧ score < +exitTh     # 15
exitShort = state = −1 ∧ score > −exitTh
```

The gap between `enterTh = 45` and `exitTh = 15` is deliberate. A single
threshold produces signal chatter around the boundary; the dead band means a
position survives normal score noise but closes when confluence genuinely decays.

### Risk levels (recorded at entry, ATR-anchored)
```
stop   = entry ∓ atrStop × ATR_14            # 2.0 × ATR
target = entry ± atrStop × ATR_14 × rr       # rr = 2.0 → 2R
```

### Cooldown
`cooldown = 8` bars between signals. Without it, a score oscillating near the
threshold generates clusters of near-identical trades that inflate the trade
count and destroy any statistical inference (the trades are not independent).

## 4. Non-negotiable execution assumptions

| Rule | Reason |
|---|---|
| Signal evaluated on **bar close** only | `barstate.isconfirmed` — intrabar signals repaint |
| Fill at **next bar open** | Filling at signal-bar close is lookahead; it is the single most common backtest lie |
| Costs applied on **both** sides | Spread + commission + slippage |
| No pyramiding in v0.1 | Keeps position accounting and trade statistics unambiguous |

## 5. Ablation requirement

The harness must be able to run AZIMUTH with any component's weight zeroed, and
report the walk-forward result for each ablation. If removing a component does
not measurably hurt out-of-sample performance, that component is decoration and
should be deleted. Expect at least one of the five to fail this test.
