# 10 — Build Roadmap

## M0 — Pine ships today ✅
- [x] `pine/AZIMUTH.pine` — indicator, dashboard, alerts, `x_*` exports
- [ ] Compile-check in TradingView Pine Editor; fix any v6 syntax rejections
- [ ] Visual sanity check on 3 instruments × 3 timeframes
- [ ] Export a fixture CSV → `tests/fixtures/`

**Exit:** indicator compiles, plots sensibly, exports parity data.

## M1 — Python core + parity 🔬
- [ ] Repo scaffold, `pyproject.toml`, CI
- [ ] `core/primitives.py` with Pine-exact ema/rma/rsi/stdev/percentrank/dmi
- [ ] `tests/test_lookahead.py` — **write this first**
- [ ] Component modules mirroring `01_SPEC_COMPONENTS.md`
- [ ] `azimuth parity` passing at 1e-6 on the fixture

**Exit:** green CI, parity gate passing. **No performance numbers exist yet and
none should be quoted.**

## M2 — Backtest engine
- [ ] Next-bar-open fill engine, cost model, trade ledger
- [ ] Metrics module
- [ ] `azimuth backtest` producing a manifest-stamped run directory
- [ ] Determinism test

**Exit:** reproducible backtests. Still not validated.

## M3 — Validation harness 🎯
- [ ] Purged/embargoed walk-forward
- [ ] Three bootstrap nulls
- [ ] Random-entry and B&H benchmarks
- [ ] DSR / PSR / SPA
- [ ] Parameter-surface plateau plot
- [ ] Pre-registration gate (hard refusal)
- [ ] `azimuth ablate`

**Exit:** the harness can produce a defensible verdict.

## M4 — The actual experiment
- [ ] Fill and commit `09_PREREGISTRATION.md`
- [ ] Stages 1–4 sweep on in-sample only
- [ ] Walk-forward + nulls + correction
- [ ] Cross-instrument test
- [ ] Holdout — **once**
- [ ] Write `results/AZIMUTH-PR-001.md`, pass or null

**Exit:** a documented answer. A null here is a completed project, not a failure.

## M5 — Conditional: operationalise
Only if M4 passes all ten criteria.
- [ ] Extract `azimuth_core` Pine library; refactor both scripts to import it
- [ ] `azimuth watch` + live-vs-TV divergence logging
- [ ] Paper-trade for a minimum of 3 months / 50 trades before any capital
- [ ] Monthly re-validation; pre-registered kill criteria (e.g. rolling 50-trade
      expectancy < 0 → halt)

## Deliberately out of scope
Broker execution · ML/optimisation layers · options · portfolio construction ·
anything that increases parameter count before M4 returns a verdict.

## Rough effort
M0 ~1 evening · M1 ~2–3 sessions (parity is fiddly) · M2 ~2 sessions ·
M3 ~3–4 sessions · M4 mostly compute + writeup.
