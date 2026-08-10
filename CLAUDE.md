# CLAUDE.md — AZIMUTH project instructions

## What this project is
A composite trading-signal engine (Pine v6 indicator + Python validation CLI).
The **primary deliverable is a verdict on whether the signal has an edge**, not
a trading system. Treat the validation harness as the product.

## Non-negotiable rules 🔒

1. **No lookahead. Ever.**
   - HTF values use confirmed bars only (`s[1]`, `lookahead_off` in Pine;
     `.shift(1)` after right-closed resample in Python).
   - Fills at next bar's open, never the signal bar's close.
   - `tests/test_lookahead.py` must exist and pass before any performance number
     is computed or quoted.

2. **Parity before performance.**
   Do not report backtest metrics until `azimuth parity` passes at 1e-6 against
   the committed Pine fixture. A Python-only result describes a system that is
   not the one on the chart.

3. **Pre-registration gate.**
   `azimuth validate` hard-errors unless `docs/09_PREREGISTRATION.md` is filled
   in and its SHA-256 is in the run manifest, recorded before the sweep ran.
   Do not add a bypass flag. Do not "temporarily" disable it.

4. **Count every trial.**
   Maintain `runs/N_trials.txt` cumulatively across the project's lifetime. It
   feeds the Deflated Sharpe Ratio. Never reset it.

5. **A null result is a success.**
   If the criteria in `docs/05_SPEC_VALIDATION.md` §6 fail, write it up in
   `results/` and stop. Do not add components, extend the sample, or re-tune to
   rescue it — that is exactly how overfits are manufactured.

6. **No `pandas_ta` or `TA-Lib`.** Their EMA/RSI seeding differs from Pine and
   will silently break parity. Implement primitives in-repo.

7. **Pine and Python cores must not drift.** Extract `azimuth_core` as a Pine
   library, or run `scripts/check_pine_parity.py` in CI.

## Working style
- Read `docs/` before writing code; the specs are authoritative over intuition.
- Small commits mapped to roadmap milestones (`docs/10_ROADMAP.md`).
- Every module gets tests in the same PR.
- Prefer explicit, boring, readable numpy/pandas over clever vectorisation.
- Use `uv` for env and dependency management.
- Type hints everywhere; `mypy --strict` on `azimuth/core/` and `azimuth/validate/`.

## Known traps (from `docs/06_PARITY_TESTS.md`)
- `pandas.rolling().std()` defaults to `ddof=1`; Pine uses population `ddof=0`.
- `ewm(adjust=False)` seeds with the first observation; Pine seeds EMA with SMA.
- `ta.percentrank` excludes the current bar and counts strictly-less-than.
- `ta.dmi` uses Wilder smoothing throughout; most library ADX implementations differ.
- Pivot functions confirm `legs` bars late — reproduce the lag, don't remove it.

## Tone
Report results plainly. If something doesn't work, say so. Do not soften a null.
