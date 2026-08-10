# 05 — Validation Protocol 🔬

> The default hypothesis is that AZIMUTH has no edge. This document describes
> what would have to happen for that to be rejected.

## 0. Order of operations (enforced by the CLI)

1. Fill in `09_PREREGISTRATION.md`. Commit it. Record its SHA-256.
2. Run the sweep on **in-sample data only**.
3. Run walk-forward validation.
4. Run permutation and benchmark nulls.
5. Apply multiple-testing correction.
6. Only then touch the holdout.
7. Write the result — **including if it is null**.

The holdout may be touched **once**. If you look at it and then change anything,
the holdout is burned and must be replaced with genuinely unseen data.

## 1. Data splits

| Split | Share | Use |
|---|---|---|
| In-sample | 50% (earliest) | Parameter sweep |
| Walk-forward | 30% | Rolling out-of-sample estimate |
| Holdout | 20% (latest) | Single final confirmation |

Plus **cross-instrument holdout**: parameters fitted on instrument A must be
tested unchanged on instruments B, C, D. A rule that only works on the asset it
was fitted to is a fitted rule.

## 2. Purging and embargo

Because AZIMUTH uses lookback windows up to 233 bars and holds positions for
multiple bars, adjacent train/test observations overlap.

- **Purge:** drop training observations whose label window overlaps the test set.
- **Embargo:** additionally drop `max(233, avg_holding_period × 3)` bars after
  each test fold before training resumes.

Skipping this inflates out-of-sample Sharpe substantially and is the most common
error in retail backtest frameworks.

## 3. Costs

Sweep costs, don't assume them:

| Scenario | Round-trip cost |
|---|---|
| Optimistic | 5 bps |
| Realistic | 15 bps |
| Pessimistic | 40 bps |
| Break-even | solve for the cost that zeroes the edge |

Report the break-even cost prominently. **If break-even cost is below your
realistic cost, the system is dead regardless of the Sharpe.** Most confluence
systems die exactly here — high trade count, thin per-trade edge.

## 4. Null models 🎲

### 4.1 Permutation null
Generate 1,000 surrogate price series that preserve the return distribution and
volatility clustering but destroy temporal structure:
- **Method A:** block bootstrap of returns (block = 20 bars) — preserves autocorrelation partially.
- **Method B:** IID shuffle of returns — destroys all structure.
- **Method C:** stationary bootstrap (Politis–Romano).

Run the full pipeline on each. AZIMUTH's real Sharpe must sit above the 95th
percentile of the surrogate distribution. Report the empirical p-value.

### 4.2 Random-entry benchmark
Random long/short entries matched to AZIMUTH on: trade count, holding-period
distribution, and long/short ratio, using the same stops/targets. This isolates
signal quality from the exit logic. It is common for a "system" to owe its entire
result to a 2R target with an ATR stop, with the signal contributing nothing.

### 4.3 Buy & hold
Both raw and volatility-matched (lever B&H to AZIMUTH's realised vol). Beating
B&H on absolute return while running 3× the volatility is not an edge.

## 5. Multiple-testing correction

Record `N` = total number of configurations evaluated across all sweeps, ever.
Not per-sweep — cumulative across the project's lifetime.

- **Deflated Sharpe Ratio** (Bailey & López de Prado): corrects observed SR for
  `N` trials, non-normal returns (skew/kurtosis), and sample length.
- **Probabilistic Sharpe Ratio:** `PSR(SR* = 0)` must exceed 0.95.
- **White's Reality Check / Hansen SPA:** tests the best configuration against
  the full set of configurations under the null of no predictive ability.

A raw Sharpe of 1.5 from 5,000 configurations is entirely consistent with noise.
DSR is what tells you whether it is.

## 6. Acceptance criteria (pre-registered)

AZIMUTH is declared to have a candidate edge **only if all** hold:

| # | Criterion | Threshold |
|---|---|---|
| 1 | Walk-forward Sharpe, realistic costs | ≥ 0.7 |
| 2 | Deflated Sharpe Ratio | > 0, PSR ≥ 0.95 |
| 3 | Permutation p-value | ≤ 0.05 across **all three** bootstrap methods |
| 4 | Beats random-entry benchmark | ≥ 95th percentile |
| 5 | Break-even cost | ≥ 2× realistic cost |
| 6 | Cross-instrument | positive WF Sharpe on ≥ 3 of 4 unseen instruments |
| 7 | Parameter stability | performance surface is a plateau, not a spike — neighbouring params within ±20% retain ≥ 60% of Sharpe |
| 8 | Holdout | consistent sign and ≥ 50% of WF Sharpe |
| 9 | Max drawdown | ≤ 25%, and ≤ B&H MaxDD |
| 10 | Trade count | ≥ 100 out-of-sample trades (else inference is meaningless) |

**Criterion 7 deserves emphasis.** A sharp spike in the parameter surface is the
signature of an overfit. A broad plateau is the signature of a real effect. Plot
it every time.

## 7. Reporting a null

If criteria fail, write `results/NULL_RESULT.md` documenting: hypothesis, method,
what was tested, where it failed, and what would change the conclusion. Publish
it. A negative result honestly documented is worth more than a tuned equity
curve — and it stops you rediscovering the same dead end in six months.

## 8. What this protocol does *not* protect against

Stated for honesty:
- **Survivorship in instrument choice** — you picked instruments that trended.
- **Regime dependence** — 2018–2026 may not resemble 2027.
- **Your own memory** — you already know what these markets did. Genuine
  pre-registration is impossible on historical data you have lived through.
- **Execution reality** — slippage in a fast market is not a constant in bps.

Treat a pass as "not yet falsified", never "proven".
