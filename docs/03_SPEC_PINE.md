# 03 — Pine v6 Implementation Spec

## 1. Structural rules

- `//@version=6` on line 1.
- Single-file indicator using `force_overlay = true` for chart-plotted elements
  (ribbon, BB, stop/target) while the score renders in its own pane.
  **Fallback:** if `force_overlay` is unavailable on the user's TV tier, split
  into `AZIMUTH_overlay.pine` and `AZIMUTH_oscillator.pine` sharing a library.
- Extract the calculation block into a Pine **library** `azimuth_core` so the
  indicator and strategy cannot drift. Until published, `scripts/check_pine_parity.py`
  must diff the two core blocks in CI and fail on mismatch.
- Max 40 `request.security()` calls. AZIMUTH uses 5 (2 HTF + 3 refs). Any new
  reference symbol must be added behind a boolean toggle so unused refs cost nothing.

## 2. Repaint contract 🔒

This is the section to get right. Everything else is cosmetic.

| Element | Rule |
|---|---|
| HTF values | `request.security(sym, tf, expr_returning_s[1], lookahead = barmerge.lookahead_off)` |
| Correlation refs | Same timeframe, `lookahead_off`. Ref series must not be forward-filled from a slower feed |
| Alerts | Fire only under `barstate.isconfirmed`, with `alert.freq_once_per_bar_close` |
| Divergence | Pivot-confirmed with `divLb` bars of lag. Lagged ≠ repainting. Do not "improve" this by reducing legs to 1 |
| `state` var | `var int` persistence; never recomputed from future bars |

**Acceptance test:** run the indicator on a replay bar-by-bar and on live data,
export both data windows, and assert every `x_*` plot matches to 1e-6. Any
mismatch is a repaint bug and blocks release.

## 3. Inputs

Grouped and inlined per the shipped file. Every magic number is an input — no
hardcoded constants in the calculation block, because the Python sweep must be
able to address all of them by the same names.

**Naming contract:** Pine input variable names and Python config keys must be
identical (snake_case in YAML, camelCase in Pine, mapped 1:1 in
`azimuth/core/params.py`). See `07_PARAMETERS.md` for the canonical table.

## 4. Plot exports for parity

Every intermediate score is plotted with `display = display.data_window` and an
`x_` prefix:

```
x_ribbon, x_bb, x_rsi, x_htf, x_corr, x_er, x_adx, x_pctb, x_bwpct, x_state
```

These are invisible on the chart but appear in **Export chart data → CSV**,
which is the input to `azimuth parity`. Do not remove them.

## 5. Alerts

Use `alert()` with a JSON payload (schema in `08_ALERTS.md`) rather than
`alertcondition()` strings, because `alert()` can embed runtime values.
`alertcondition()` entries are retained for users who want simple pop-ups.

## 6. Performance

- Avoid `request.security` inside loops.
- `ta.*` functions must be called unconditionally at global scope, never inside
  `if` blocks — Pine's execution model requires it and conditional calls produce
  silently wrong series.
- `max_bars_back = 2000` covers the 233-period EMA and 200-bar percentranks.

## 7. Known Pine gotchas to watch during build

1. `array.max()` / `array.min()` take the array id only.
2. `ta.dmi(len, smoothing)` returns a **3-tuple**; unpack all three.
3. `math.sign()` returns a float, not an int.
4. `input.timeframe()` returns a `simple string` — valid for `request.security`.
5. Function parameters used as `request.security` symbols must be `simple string`.
6. `ta.valuewhen()` requires a `simple int` occurrence argument.
7. Division guards: every denominator uses `math.max(x, 1e-10)`.
