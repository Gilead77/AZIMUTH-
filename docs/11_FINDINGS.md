# 11 — Findings Register 🔎

> **Status of this document.** These are findings raised against the specs in
> `00_README.md` … `10_ROADMAP.md`, not amendments to them. Docs 00–10 remain
> authoritative and unmodified. Nothing here changes the design until Harry marks
> an item `ACCEPTED` or `REJECTED` and the corresponding spec is edited in a
> separate, reviewable commit.
>
> Rationale for keeping them separate: several of these findings bear directly on
> the pre-registration (what counts toward `N`, what the permutation null is, how
> criterion 7 is measured). Decisions on those must be made **before** the sweep
> runs and must be attributable — an audit trail of what changed and why is part
> of the defensibility of the final verdict.

**Legend** — `UNADJUDICATED` (raised, awaiting decision) · `ACCEPTED` (spec to be
amended) · `REJECTED` (design stands as written) · `RESOLVED` (spec amended, commit
referenced).

**Blocking column** — the milestone by which a decision is required. Items marked
**M4-blocking** must be settled before `09_PREREGISTRATION.md` is signed, because
deciding them after results are visible is itself a researcher degree of freedom.

| # | Area | Spec ref | Decide by | Status |
|---|---|---|---|---|
| 1 | Regime-gate flicker | `01` §6, `02` §2 | M3 | UNADJUDICATED |
| 2 | Cooldown is inert | `02` §3, `07` §1 | M2 | UNADJUDICATED |
| 3 | Correlation calendar mismatch | `01` §5, `06` | M1 | UNADJUDICATED |
| 4 | Inert swept parameters | `07` §1–2 | M4 | UNADJUDICATED |
| 5 | Permutation null invalid for cross-asset | `05` §4.1 | M4 | UNADJUDICATED |
| 6 | `N` under-counted | `05` §5, `07` §2 | M2 | UNADJUDICATED |
| 7 | Staged sweep breaks DSR estimator | `05` §5 | M4 | UNADJUDICATED |
| 8 | Purge/embargo mislabelled; boundary rule missing | `05` §2 | M3 | UNADJUDICATED |
| 9 | Criterion 7 unfalsifiable | `05` §6 | M4 | UNADJUDICATED |
| 10 | No positive control | `05`, `10` M3 | M3 | UNADJUDICATED |
| 11 | `x_htf` "exact" tolerance | `06` §2 | M1 | UNADJUDICATED |
| 12 | `percentrank` convention conflict | `06` §3 | M1 | UNADJUDICATED |
| 13 | `atrLen` missing from parameter table | `07` §1 | M2 | UNADJUDICATED |
| 14 | Statistical power not pre-registered | `05` §6, `09` | M4 | UNADJUDICATED |
| 15 | Holdout single-touch is a promise, not a mechanism | `05` §0 | M3 | UNADJUDICATED |
| 16 | Component collinearity predicts the ablation | `02` §5 | M1 | UNADJUDICATED |
| 17 | `default.yaml` path discrepancy | `00` vs `04` §3 | M1 | UNADJUDICATED |
| 18 | `ta.pivothigh` tie-handling unspecified | `06` §3 | M1 | UNADJUDICATED |
| 19 | Fixture export cannot verify `x_corr` | `06` §1–2 | M1 | **RESOLVED** — commit 4 |
| 20 | `htfCalc` hardcodes 14 and 3 | `03` §3, `07` §1 | M2 | UNADJUDICATED |
| 21 | **HTF resample `closed="right"` is wrong** | `04` §6 | M1 | UNADJUDICATED ⚠️ |
| 22 | A boolean toggle does not gate `request.*` | `03` §1 | M2 | UNADJUDICATED |
| 23 | **Stateful `ta.*` behind short-circuiting `and`** | `03` §6 | M1 | **FIXED** — commit 6 ⚠️ |
| 24 | Continuation indented by a multiple of 4 | — | M1 | **FIXED** — commit 6 |

Fixed in code already (not awaiting adjudication):

| # | Area | Status |
|---|---|---|
| 0 | `crowding` operator precedence, `pine/AZIMUTH.pine:177` | **FIXED** — commit 1 |
| 0b | `ruff format` silently edits Python snippets inside `docs/*.md` | **FIXED** — commit 2 |

**0b** deserves a note despite being a one-line config fix. `ruff format .` reformatted
a code fence inside `04_SPEC_PYTHON_CLI.md` §6 on its first run. Had it reached
`09_PREREGISTRATION.md`, it would have changed that file's bytes and therefore its
SHA-256 — invalidating a live registration through nothing but a whitespace tweak, and
the gate would have reported the registration as edited-after-the-fact. `docs/` and
`pine/` are now in `extend-exclude` in `pyproject.toml`. Formatters must never be
pointed at the specification.

---

## 0. `crowding` operator-precedence bug ✅ FIXED

**Where:** `pine/AZIMUTH.pine:177`.

Pine's conditional operator `?:` has lower precedence than `+`. The original
denominator

```pine
math.max(useC1?1:0 + (useC2?1:0) + (useC3?1:0), 1)
```

parses as `useC1 ? 1 : (0 + (useC2?1:0) + (useC3?1:0))`, so with the default
`useC1 = true` it evaluates to **1 unconditionally**. `crowding` therefore sums two
or three `|ρ|` values and divides by 1, and can exceed its documented range of
`[0, 1]`.

**Impact:** `crowding` reaches the dashboard and the `08_ALERTS.md` payload. It does
**not** enter `score`, any `x_*` export, or `x_state`, so no signal behaviour changes
and every parity assertion in `06` §2 is unaffected. It would matter to the
`--crowding-haircut` proposal in `01` §7.

**Fix applied:** parenthesised, with an explanatory comment so it is not
"simplified" back. Done before the fixture export so the parity ground truth is not
cut from buggy code.

---

## 1. The regime gate flips the score's sign with no hysteresis

**Where:** `01` §6, `02` §2. **Decide by M3.**

`trending = ER > 0.30 OR ADX > 20` inverts the polarity of both `bbScore` and
`rsiScore`. With default weights (`wSum = 4.3`), a single flip of that boolean moves
the composite by up to

```
2 × (w_BB × 1 + w_RSI × 1) / wSum × 100  =  2 × 1.6 / 4.3 × 100  ≈  74 points
```

with **no price movement required**. That exceeds `enterTh = 45`, so an entry can be
triggered by ADX ticking from 19.98 to 20.02.

`02` §3 identifies exactly this failure mode for the score itself — "a single
threshold produces signal chatter around the boundary" — and fixes it with the
45/15 dead band. The gate that *inverts* that score has no equivalent protection.
This is an internal inconsistency in the design, not a missing feature.

Second-order: `OR` ratchets the gate toward "trending". If ADX(14) > 20 holds on a
majority of bars for liquid instruments and `ER > 0.30` adds more, then "range" is a
rare and short-lived state — meaning the mean-reversion branch is fitted on a small,
unrepresentative subsample.

**Proposed amendment:** none yet — this needs measurement first, because any fix is
a design change and therefore a new hypothesis. Add to M1 as a **descriptive
diagnostic** (permitted before the parity gate; it is not a performance metric):

- regime duty cycle: fraction of bars where `trending` is true;
- flip frequency and mean run length of each regime state;
- the same, restricted to bars where `|score|` is within ±10 of `enterTh`.

Decision rule to pre-commit: if range mode occupies < 20% of bars **or** mean run
length is < 5 bars, record in the pre-registration that the polarity switch is
expected to act as noise amplification, and treat the adaptive/trend-only/range-only
modes (`01` §6) as the three genuinely separate hypotheses they are already declared
to be.

---

## 2. `cooldown` is almost certainly inert

**Where:** `02` §3, `07` §1. **Decide by M2.**

`pine/AZIMUTH.pine:216,221` set `lastBar := bar_index` on entry only. `lastBar` is
never updated on exit (line 224). So `cooled = bar_index - lastBar >= cooldown`
measures time since the last **entry**, not time since the last signal of any kind.
If the mean holding period exceeds `cooldown = 8` bars — which it near-certainly
does for a 2R/2×ATR structure — the gate never binds.

Compounding this, `ta.crossover(score, enterTh)` already requires the score to fall
below the threshold and cross back up, which suppresses most of the chatter `02` §3
attributes to the cooldown.

**Impact if confirmed:** `signal.cooldown_bars` swept over 0–20 contributes ~20
configurations to `N` that cannot change any result. See also finding 6 — inert
trials still inflate `N` and therefore make the DSR correction *more* conservative,
so this is not a correctness risk, but it is wasted compute and a misleading entry
in the pre-registration's parameter table.

**Proposed amendment:** measure at M2 — count signals blocked by `cooled` alone,
with defaults. If zero, either drop `signal.cooldown_bars` from the sweep and note
it in `07` §2, or change the semantics to "bars since last state *change*" — the
latter is a design change requiring a new registration.

---

## 3. Correlation references with mismatched trading calendars

**Where:** `01` §5, `06`. **Decide by M1.**

`request.security(sym, timeframe.period, close, lookahead = barmerge.lookahead_off)`
returns the last available value when the reference instrument is not trading. For a
reference on a different calendar this injects **structural zero returns**:

| Instrument | Reference | Effect |
|---|---|---|
| BTC (24/7) | `TVC:DXY` (24/5) | every weekend bar has `r_ref = 0` |
| BTC 1H (24/7) | `SP:SPX` (~6.5h/day) | ~73% of bars have `r_ref = 0` |

A 60-bar correlation on a series that is ~73% structural zeros is computed on
roughly 16 real observations. `ρ` is biased toward zero, and the `|ρ| ≥ corrMin`
gate fires erratically.

**This is not a parity bug.** Pine forward-fills and a pandas `reindex(...).ffill()`
forward-fills identically, so `azimuth parity` will agree at 1e-6 on a number that
carries almost no information. It is the clearest case in the project where parity
is necessary but not sufficient, and `06` does not mention it.

**Proposed amendment:** add to `01` §5 a requirement that references either share a
trading calendar with the instrument, or that `ρ` be computed only over bars where
the reference actually printed a new value (with the effective window length
reported). Add to M1 the diagnostic *effective reference observations ÷ `corrLen`*,
per reference, per bar — reported as a distribution.

---

## 4. Four swept parameters cannot affect any metric

**Where:** `07` §1–2. **Decide by M4.**

`ribCompress` (`pine/AZIMUTH.pine:128`) and `bbSqueeze` (line 135) reach only
`bgcolor` (238), the dashboard (277), the BB fill colour (258) and one
`alertcondition` (303). Neither enters `score`, `trending`, or the state machine.

`07` §1 nevertheless lists as swept: `ribbon.compress_lookback` (100–300),
`ribbon.compress_pctile` (10–30), `bollinger.bw_lookback` (100–300),
`bollinger.squeeze_pctile` (10–30).

Every cell varying only these will return an identical result.

**Proposed amendment:** drop the four from the sweep grid and from the
pre-registration's stage tables; keep them as configurable inputs for the chart. The
alternative — wiring compression into the signal — adds a component and is out of
scope before M4 returns a verdict (`10`, "Deliberately out of scope").

---

## 5. The permutation null is not a null for the correlation component ⚠️

**Where:** `05` §4.1. **Decide by M4. This one is a correctness hole, not a
refinement.**

`05` §4.1 specifies surrogate series for the traded instrument. If the instrument's
returns are permuted while the reference series (`DXY`, `SPX`, `GOLD`) are left
intact, then in every surrogate:

- `ρ_j = correlation(r_own_shuffled, r_ref)` → ≈ 0;
- `|ρ_j| ≥ corrMin` fails for all *j*;
- `corrScore` → 0 on essentially every bar.

The surrogate strategy is therefore a **four-component system**, while the observed
strategy is a five-component system. Comparing one to the other does not test the
null hypothesis of no predictive ability; it tests a different strategy.

**Proposed amendment:** to `05` §4.1 — the permutation must be applied as a **single
shared index permutation across all series simultaneously** (own OHLCV and every
reference), which destroys temporal structure while preserving contemporaneous
cross-sectional dependence. For the block and stationary bootstraps, the same block
indices must be drawn once and applied to all series. Document that this preserves
`ρ` by construction, which is the point: the null must retain everything except the
time ordering the signal claims to exploit.

---

## 6. `N` is under-counted by construction

**Where:** `05` §5, `07` §2. **Decide by M2 (implementation), M4 (accounting).**

`07` §2 arrives at cumulative `N ≈ 760` from the four sweep stages. Not included:

- ablation runs (`02` §5) — one per component, plus combinations;
- the three `regime.mode` values declared "separate hypotheses" (`01` §6);
- the mandatory equal-weight baseline (`02` §1);
- cross-instrument runs (`05` §1, criterion 6);
- every exploratory or debugging backtest whose Sharpe was displayed.

The operative rule for a DSR correction is: **`N` is the number of Sharpe values you
have observed**, not the number you intended to observe.

**Proposed amendment:** make it mechanical rather than clerical. `runs/N_trials.txt`
is incremented **by the harness**, once per backtest evaluation that produces a
Sharpe, at the point of computation — in `azimuth/backtest/metrics.py`, not by hand
and not by the sweep driver (which would miss single runs). Implement at M2, before
any metric exists to be counted. Add a CI test asserting that the counter is
append-only and monotonically non-decreasing across commits.

---

## 7. The staged sweep breaks the standard DSR estimator

**Where:** `05` §5, `07` §2. **Decide by M4.**

Bailey & López de Prado's Deflated Sharpe Ratio computes the expected maximum
Sharpe under the null from `N` trials and the **variance of the trial Sharpes**,
assuming the trials are draws from a single family.

`07` §2's staged design breaks that assumption: stage 2 sweeps thresholds
*conditional on stage 1's winner*, stage 3 conditional on stage 2's, and so on. The
staging is itself a selection step, and it is not represented in the estimator.
Applying the vanilla formula to `N = 760` pooled trials **understates** the
correction.

**Proposed amendment:** pre-commit to one treatment in `09_PREREGISTRATION.md`
§3–4, before any results exist:

- **(a)** compute DSR per stage using that stage's `N` and trial variance, and
  report the most conservative; or
- **(b)** treat `N` as the full lifetime count with the pooled variance of all
  observed Sharpes — cruder, more conservative, simpler to defend.

(b) is the recommendation. Whichever is chosen, choosing it *after* seeing whether
the result passes is precisely the degree of freedom the pre-registration exists to
remove.

---

## 8. Purge/embargo is mislabelled; the real gap is the fold-boundary trade rule

**Where:** `05` §2. **Decide by M3.**

`05` §2 uses López de Prado's purging and embargo vocabulary, which is designed for
**supervised learners trained on observations with overlapping label windows**.
AZIMUTH trains nothing: it is a fixed rule whose parameters are chosen by grid
search over a performance metric. "Drop training observations whose label window
overlaps the test set" has no referent, because there are no training observations
and no labels.

Implementing literal LdP purging would spend effort on machinery with nothing to
operate on. What the protocol actually needs, and what genuinely leaks if omitted:

1. **Warmup isolation.** The longest lookback is 233 bars (`ribbon.lengths[7]`),
   with 200-bar percentranks and a 60-bar correlation behind it. Every fold must
   begin with its indicators warmed from data *inside* that fold's own history, or
   the first ~283 bars of each test fold carry state fitted on training data. The
   embargo as specified (`max(233, avg_holding × 3)`) achieves this — it is correctly
   sized, just misnamed.
2. **Fold-boundary trades.** *Currently unspecified anywhere.* A position open when
   a fold ends must be handled by a stated rule: force-close at the boundary bar's
   close, or exclude the trade from both folds. Leaving it implicit means the answer
   depends on an implementation accident, and mark-to-market of an open position
   across a boundary is a real leakage channel.

**Proposed amendment:** rewrite `05` §2 as "Warmup isolation and fold-boundary
handling", keep the embargo formula unchanged, drop the purge language, and add an
explicit boundary-trade rule. Recommendation: **force-close at the boundary close,
with the count and P&L of boundary-closed trades reported separately**, so their
contribution is visible rather than buried.

---

## 9. Criterion 7 (parameter plateau) is unfalsifiable as written

**Where:** `05` §6, criterion 7. **Decide by M4.**

> "performance surface is a plateau, not a spike — neighbouring params within ±20%
> retain ≥ 60% of Sharpe"

Across 8+ swept parameters, "neighbouring params within ±20%" is undefined: jointly
(a hypercube corner, where almost nothing survives) or marginally (one dimension at
a time)? Over which parameters — all swept, or only the continuous ones? `regime.mode`
and `ribbon.lengths` are categorical and have no ±20%.

As written the criterion can be satisfied or refuted at will after the fact, which
makes it the weakest seam in an otherwise tight protocol.

**Proposed amendment:** pin a concrete metric in `09` before the sweep. Suggested:

> For each **continuous** swept parameter *p* independently, hold all others at the
> selected configuration and take the mean walk-forward Sharpe over the grid points
> within ±20% of the selected value of *p*. Criterion 7 passes if that mean is
> ≥ 60% of the selected configuration's Sharpe **for every** *p*. Categorical
> parameters are excluded and reported separately as a sensitivity table.

Report the full marginal profile per parameter regardless of pass/fail — the shape
is more informative than the boolean.

---

## 10. No positive control on the harness 🎛️

**Where:** `05` (absent), `10` M3. **Decide by M3.**

Every criterion in `05` §6 can fail for uninteresting reasons: a sign error in the
cost model, an off-by-one in fold boundaries, a fill applied on the wrong bar. If the
harness is silently destroying signal, a null result is **uninterpretable** — it
looks identical to an honest null, and the project's central deliverable is exactly
the ability to tell those apart.

**Proposed amendment:** add to M3's exit criteria two synthetic signals run through
the *entire* pipeline before AZIMUTH is:

| Control | Signal | Harness must report |
|---|---|---|
| **Known-dead** | coin-flip entries, seeded | permutation p ≈ 0.5, DSR ≤ 0, no criterion passes |
| **Known-cheating** | deliberate 1-bar lookahead (enter long when the *next* bar closes up) | an implausibly high Sharpe, all criteria passing |

The cheating control is the important one. If a signal with perfect one-bar
foreknowledge does **not** produce an absurd Sharpe, there is a bug between the
signal and the metric, and every subsequent number is worthless. It is the cheapest
insurance in the project.

Both controls must live in `tests/` and run in CI, not as one-off scripts. The
cheating control must be constructed so it cannot be imported by production code
paths — `tests/controls/` with no import from `azimuth/`.

---

## 11. `x_htf` tolerance "exact" fails on correct code

**Where:** `06` §2. **Decide by M1.**

`06` §2 sets the `x_htf` tolerance to "exact — categorical ±1/3 steps; any mismatch
= alignment bug". But `htfScore = clip(0.6 × h1 + 0.4 × h2)` where each `h` ∈
{−1, −1/3, +1/3, +1}. Neither `1/3`, `0.6 × (1/3)`, nor their sum is exactly
representable in IEEE 754 binary64 — e.g. `0.6 * (1.0/3.0)` evaluates to
`0.19999999999999998`, and Pine's and NumPy's rounding of the intermediate products
need not agree bit-for-bit.

Strict float equality will therefore fail on a correct implementation.

**Proposed amendment:** to `06` §2 — tolerance `1e-9`, plus the assertion the
"exact" was really reaching for: the set of **distinct values** taken by `x_htf`
must have cardinality ≤ 16 and each must be within `1e-9` of a member of
`{0.6a + 0.4b : a, b ∈ {−1, −⅓, ⅓, 1}}` after clipping. That catches genuine
alignment bugs (which produce off-lattice values) without failing on float noise.

---

## 12. `ta.percentrank` convention conflict ⚠️

**Where:** `06` §3. **Decide by M1 — the fixture settles it.**

`06` §3 specifies:

> % of prior values **strictly less than** current, over `len` **excluding** current

TradingView's own reference for `ta.percentrank` states:

> the percent of how many previous values were **less than or equal to** the current
> value of the given series

These disagree on the tie-handling. It matters for `ribWidthPc` and `bwPct`, both
compared against a 20th-percentile threshold, where ties in a bounded, slowly-varying
series are not rare.

**Handling in code (already applied, not a spec change):** implemented behind a
single module-level constant `_PCTRANK_STRICT` in `azimuth/core/primitives.py`,
defaulting to `06` §3's reading (strict `<`) since the spec is authoritative.
`tests/test_percentrank_convention.py` pins the current behaviour and documents both
conventions, so flipping the constant is a one-line change with a test that
immediately shows the difference.

**Resolution path:** the Pine fixture export decides it empirically. Compare
`x_bwpct` against both conventions on the fixture; whichever matches at 1e-6 is
correct, and `06` §3 gets amended to match reality.

---

## 13. `atrLen` has no row in the parameter table

**Where:** `07` §1. **Decide by M2.**

`pine/AZIMUTH.pine:95` declares `atrLen = input.int(14, "ATR length", ...)`. It feeds
`ribSlope` normalisation (line 123) and the stop/target distances (217–222), so it
affects both the composite score and the risk levels. `07` §1 lists `atrStop` and
`rrTarget` but not `atrLen`.

`03` §3 states the naming contract: "Every magic number is an input — no hardcoded
constants in the calculation block, because the Python sweep must be able to address
all of them by the same names."

**Handling in code:** added as `risk.atr_length` (default 14) in
`config/default.yaml` and the pydantic schema, marked with a `FINDING-13` comment.

**Proposed amendment:** add the row to `07` §1. Recommendation: **do not sweep it.**
It appears in both the score normalisation and the stop distance, so sweeping it
changes two things at once and its effect is uninterpretable. Fix at 14.

---

## 14. Statistical power is not pre-registered

**Where:** `05` §6, `09` §2. **Decide by M4.**

Criterion 10 requires ≥ 100 **out-of-sample** trades. Out-of-sample is the 30%
walk-forward slice (`05` §1), so the full sample must yield roughly 330+ trades to
satisfy it — before considering that criterion 6 wants the same machinery to produce
usable counts on four further instruments.

Entry requires the conjunction `crossover(score, 45) ∧ cooled ∧ trending ∧
htfScore > 0` (`pine/AZIMUTH.pine:210`). Each conjunct is individually plausible;
together they may bind hard. `07` §3 already flags "4H: fewest trades; may fail
criterion 10", but the deeper issue is undiscussed:

**A failure to reject H₀ on an underpowered sample is not evidence of no edge.** The
project's stated goal is a *defensible verdict*, and "we could not have detected an
effect of this size" is a materially different verdict from "there is no effect".

**Proposed amendment:** add to `09` a pre-registered power statement:

- expected trade count on the chosen instrument/timeframe with default parameters,
  measured at M2 (a trade count is not a performance metric — it can be computed
  before the parity gate lifts);
- the **minimum detectable Sharpe** at 80% power given the walk-forward sample length
  and that trade count;
- an explicit commitment: if MDS > 0.7, criterion 1 is not a test, and the outcome is
  reported as *underpowered*, not as a null.

Choosing the instrument or timeframe *after* seeing the trade count is a researcher
degree of freedom — so this measurement must precede signing the registration, and
the choice must be recorded in it.

---

## 15. The holdout single-touch rule is a promise, not a mechanism

**Where:** `05` §0, §8. **Decide by M3.**

> "The holdout may be touched **once**. If you look at it and then change anything,
> the holdout is burned."

`05` §8 is admirably honest that "your own memory" is unprotectable. But the
single-touch rule is currently enforced by intention alone, while the
pre-registration gate — a comparable discipline — is enforced by a hard error with
no bypass flag (`04` §4, `CLAUDE.md` rule 3). The asymmetry is unnecessary.

**Proposed amendment:** make it mechanical. Any command touching holdout data
appends an immutable record to `runs/holdout_touches.log` — timestamp, registration
ID, git SHA, config hash, data hash, result — and **refuses to run** for an
(instrument, registration-ID) pair already present, without a new registration ID.
Same posture as the pre-registration gate: hard error, no bypass.

---

## 16. Component collinearity likely predetermines the ablation

**Where:** `02` §5. **Decide by M1 — this is cheap and worth knowing early.**

`02` §5 expects "at least one of the five to fail" the ablation. Inspection of the
construction suggests the finding may be larger than one component, and that it is
predictable before any backtest:

- `ribScore` = 0.65 × EMA stacking order + 0.35 × ATR-normalised EMA-34 slope;
- `bbScore` (trend branch) = `(%B − 0.5) × 2`, i.e. a scaled z-score of close against
  a 20-bar SMA;
- `rsiScore` (trend branch) = `(rsi − 50)/25`.

All three are momentum/location measures on the same `close` series over comparable
horizons. `02` §1 already concedes RSI is "partially collinear with ribbon". `htfScore`
is the same family of measurement at a slower sampling rate.

The correlation component is structurally different but rests on a stronger claim
than the spec states: `01` §5 justifies `contrib_j = ρ_j × sign(ref − EMA(ref, 50))`
as "the reference is trending up; we are positively correlated with it; therefore up
is favoured". That reasoning requires the reference's *trend* to predict our *next-bar
return*, whereas `ρ` measures **contemporaneous** return correlation. Correlation is
not lead-lag; a high contemporaneous `ρ` is consistent with zero predictive content.

**Proposed amendment:** add to M1's exit criteria a **pairwise correlation matrix of
the five component scores**, computed on the in-sample data. This is a descriptive
statistic of the signal, not a performance metric, so it does not breach `CLAUDE.md`
rule 2 or the M1 exit condition.

If ρ(ribbon, bb) and ρ(ribbon, rsi) exceed ~0.6, the likely ablation outcome —
*any two of {ribbon, BB, RSI} can be zeroed at no out-of-sample cost* — can be stated
**in the pre-registration as a prediction**, rather than discovered afterwards. A
pre-registered prediction that comes true is far stronger evidence than the same
observation made post hoc, and it costs nothing to make now.

---

## 17. `default.yaml` lives in two places in the docs

**Where:** `00_README.md` repo layout vs `04_SPEC_PYTHON_CLI.md` §3. **Decide by M1.**

The two layout sketches disagree:

- `00` puts `config/default.yaml` at the repo root, and every command example in
  `04` §4 passes `--config config/default.yaml`;
- `04` §3 puts it inside the package at `azimuth/config/default.yaml`, alongside
  `schema.py`.

**Handling in code:** `azimuth/config/default.yaml` is treated as canonical, per
`04` §3 — it is the section the build task cites, and it is the only location that
survives `pip install`, so `load_default()` works from an installed package rather
than only from a source checkout. A repo-root `config/` directory is retained for
run inputs that genuinely are not package data (`grid.yaml`, per `04` §4's
`azimuth sweep --grid config/grid.yaml`), with a README pointing at the canonical
file. `--config <path>` accepts any path, so the `04` §4 examples still work.

**Proposed amendment:** correct the `00` layout sketch to match `04` §3. Trivial,
but worth doing before someone creates a second `default.yaml` and the two drift.

---

## 18. `ta.pivothigh` / `ta.pivotlow` tie-handling is unspecified

**Where:** `06_PARITY_TESTS.md` §3. **Decide by M1 — the fixture settles it.**

`06` §3 specifies the confirmation lag for the pivot functions but not the
comparison used against the flanking bars. On an exactly-flat top — say
`[…, 9, 9, 9, …]` — whether a bar counts as a pivot depends on whether the
comparison is strict (`>`) or inclusive (`>=`), and whether the two sides use the
same one. TradingView's documentation does not pin this down either.

It only matters on exact ties, which are rare in continuous price data but not rare
in the series AZIMUTH actually feeds these functions: `pine/AZIMUTH.pine:140-141`
takes pivots of **RSI**, which is bounded, quantised by its own smoothing, and
genuinely does repeat values on quiet bars. The divergence bonus is `±0.35` — about
6.5 score points at the default RSI weight — so a spurious or missed pivot is not
negligible.

**Handling in code:** behind `PIVOT_STRICT_BOTH` in `azimuth/core/primitives.py`,
defaulting to strict on both flanks. Same pattern as finding 12: one constant, one
line to flip, with `tests/test_pivot_lag.py` pinning current behaviour.

**Resolution path:** the fixture decides. The confirmation *lag* is not in question
and is not configurable — it is asserted independently in
`tests/test_pivot_lag.py` and by the lookahead property test, so settling the tie
convention cannot accidentally loosen the thing that actually matters.

---

## 19. The fixture export could not verify `x_corr` ✅ RESOLVED

**Where:** `06_PARITY_TESTS.md` §1–2. **Fixed in commit 4, before the first export.**

`06` §1 defines the parity procedure as: load the indicator, export chart data to CSV,
run `azimuth parity` against it. `06` §2 then assigns `x_corr` a tolerance of 1e-5.

But a TradingView chart-data export contains the base symbol's OHLCV plus the plotted
series — and the correlation component's **inputs are neither**. The reference closes
arrive through `request.security` inside `refPack()` (`pine/AZIMUTH.pine:161-168`) and
are never plotted, so the export carries `x_corr` with nothing to recompute it from.
Comparing our `x_corr` against Pine's would require sourcing DXY/SPX from a different
vendor at matching timestamps, which introduces a second discrepancy exactly where the
first one is being measured.

The consequence is worse than "one component unverified". Correlation is the component
most likely to fail the ablation (finding 16), so it is the one whose numbers most need
to be trustworthy before anyone concludes anything from them.

**Fix applied:** `refPack()` now returns the reference close alongside its derived
values, and the export gains `x_ref1..3`, `x_rho1..3` and `x_crowd`. Python can
recompute the full chain — log returns → rolling ρ → EMA trend sign → `|ρ|` gate →
weighted contribution — and localise a mismatch to one step rather than reporting that
the endpoint disagrees. No new `request.security` calls: still 5 against Pine's limit
of 40 (`03` §1).

`x_crowd` is included because `crowding` was the subject of the finding 0 precedence
bug; exporting it is the only way to confirm the fix is live on the chart and not just
in the file.

**Proposed amendment:** add the new series to `06` §2's assertion table. Suggested
tolerances: `x_ref*` 1e-6 (raw prices), `x_rho*` 1e-5 (matching `x_corr`), `x_crowd`
1e-6.

---

## 20. `htfCalc` hardcodes two constants

**Where:** `03_SPEC_PINE.md` §3, `07_PARAMETERS.md` §1. **Decide by M2.**

`pine/AZIMUTH.pine:150-151`:

```pine
hr = ta.rsi(close, 14)                                  // 14 hardcoded
sc = (((close > he ? 1 : -1) + (he > he[3] ? 1 : -1) + ...) / 3.0)   // 3 hardcoded
```

`03` §3 is unambiguous: "Every magic number is an input — no hardcoded constants in the
calculation block, because the Python sweep must be able to address all of them by the
same names." Neither value appears in `07` §1 either.

The RSI length is the more substantive of the two. The chart-timeframe RSI is
configurable via `rsiLen` (default 14, sweep range 9–21), but the HTF RSI feeding
`htfScore` is pinned at 14 regardless. A sweep over `rsi.length` therefore changes one
of the two RSI computations and silently leaves the other — so the swept parameter does
not mean what its name implies, and HTF bias, the **highest-weighted component** at
1.2, is partly outside the parameter space being searched.

**Handling in code:** added as `htf.rsi_length` (14) and `htf.slope_lookback` (3),
defaulting to exactly what Pine hardcodes, so behaviour is byte-identical and parity is
unaffected. `PINE_TO_YAML` lists them under the names the Pine inputs should take
(`htfRsiLen`, `htfSlopeLb`) so the contract is recorded now and bringing Pine into line
later needs no second rename.

**Proposed amendment:** add both rows to `07` §1 and the inputs to `AZIMUTH.pine`.
Recommendation on sweeping: **tie `htf.rsi_length` to `rsi.length`** rather than
sweeping it independently — they measure the same thing at two sampling rates, and
varying them separately adds a dimension without adding a distinct hypothesis. Leave
`htf.slope_lookback` fixed at 3.

---

## 21. The HTF resample snippet takes the wrong window ⚠️

**Where:** `04_SPEC_PYTHON_CLI.md` §6. **Decide by M1. Code already deviates from the
spec — flagging loudly because this one changes numbers.**

`04` §6 gives the HTF construction as:

```python
htf = df.resample(rule, label="right", closed="right").agg(OHLCV_AGG)
```

`closed="right"` is wrong for this data, and it shifts every HTF bar's contents by one
base bar.

Canonical-frame timestamps are bar **open** times — that is what TradingView's chart
export, yfinance and ccxt all return, and `04` §5 does not say otherwise.
`closed="right"` therefore builds the half-open interval `(00:00, 04:00]`, so the 4H
bar aggregates the 1H bars at 01:00, 02:00, 03:00 and 04:00. TradingView's 4H bar
covers 00:00, 01:00, 02:00, 03:00.

Measured on a 1H series with closes 1.0 … 8.0:

| Setting | Bars aggregated | `open` | `close` |
|---|---|---|---|
| spec — `closed="right"` | 01:00–04:00 | 2.0 | 5.0 |
| **correct — `closed="left"`** | **00:00–03:00** | **1.0** | **4.0** |
| TradingView | 00:00–03:00 | 1.0 | 4.0 |

Every OHLC field comes from the wrong window: the bar that opens the HTF period is
dropped, and one belonging to the *next* period is swallowed. Downstream that
corrupts `he = EMA(close, 50)`, `hr = RSI(close, 14)` and the `he > he[3]` slope
term — i.e. all three votes in `01` §4 — for the **highest-weighted component** at 1.2.

It is easiest to see at the daily boundary, where `closed="right"` puts a day's 00:00
bar into the *previous* day's daily bar.

**Why it deserves emphasis beyond being a one-word fix.** The failure presents as an
`x_htf` parity mismatch of roughly one bar, and the intuitive response to a one-bar
mismatch is to adjust the `.shift(1)`. That trades a grouping error for a **lookahead**
error, makes parity pass, and makes the backtest better — which is precisely the
sequence `CLAUDE.md` rule 1 and `04` §6's own warning exist to prevent. The grouping
and the shift are independent; only the shift is about lookahead.

**Handling in code:** `azimuth/data/resample.py` uses `closed="left", label="right"`,
with the deviation documented at the top of the module and at the call.
`tests/test_data_layer.py::test_spec_closed_right_takes_the_wrong_window` pins the
difference so the spec's snippet cannot be pasted back in, and
`test_daily_bar_covers_one_calendar_day` covers the daily case.

**Proposed amendment:** correct the snippet in `04` §6 to `closed="left"`, and add a
sentence stating that canonical-frame timestamps are bar-open times — the whole
question turns on that, and the spec never says it.

---

## 22. A boolean toggle does not make an unused reference free

**Where:** `03_SPEC_PINE.md` §1. **Decide by M2.**

`03` §1 states:

> Any new reference symbol must be added behind a boolean toggle so unused refs
> cost nothing.

That is false. Pine issues every `request.*()` call on every bar regardless of any
guarding ternary — `on ? request.security(...) : na` selects between the *results*,
it does not skip the request. The `useC1/2/3` toggles therefore save nothing.

The call budget is not the problem: 3 `request.security` call sites, 5 at runtime,
against `03` §1's limit of 40. The problem is the **third default reference**.
`corr.references[2]` is `TVC:GOLD` with `enabled: false`, and Pine fetches it
anyway — so an unavailable or mistyped ticker can produce a load error on a
reference the user believes is switched off, with nothing on screen to connect the
two.

**Proposed amendment:** correct the sentence in `03` §1 — a toggle gates the
reference's *contribution*, not its cost. Recommend the third default reference be
cleared to an empty symbol rather than merely disabled, so the shipped default
fetches only what it uses.

---

## 23. Stateful `ta.*` calls behind short-circuiting operators ✅ FIXED

**Where:** `03_SPEC_PINE.md` §6. **Fixed in commit 6.** Surfaced by the first
TradingView compile (CW10002).

`03` §6 says:

> `ta.*` functions must be called unconditionally at global scope, never inside
> `if` blocks — Pine's execution model requires it and conditional calls produce
> silently wrong series.

The rule is right; the *scope* is too narrow. It names `if` blocks, but the form
that actually occurred three times in the shipped indicator is a short-circuiting
`and` or a ternary. A stateful `ta.*` after `x and …` is skipped whenever `x` is
false, and its internal history desynchronises exactly as it would inside an `if`.

| Site | Call | Reaches |
|---|---|---|
| `142-145` | `ta.valuewhen` × 8, behind `plF and …` | `x_rsi`, via the divergence bonus |
| `218-219` | `ta.crossover` / `ta.crossunder`, behind `state <= 0 and …` | **`x_state`** |
| `169-170` | `ta.correlation`, `ta.ema`, behind `on ? … : na` | `x_corr`, `x_rho*` |

**The middle row is the serious one, and it is not a parity problem.**
`ta.crossover(score, enterTh)` needs the previous bar's score. While a position is
open, `state <= 0` is false, so the call may be skipped; when the position closes
and state returns to 0, the function's notion of "previous bar" is stale. The first
bar after every exit can therefore report a cross that did not happen, or miss one
that did. That is wrong signals on the live chart, independent of any Python
comparison — and `x_state` is the series `06` §2 compares at **exact** tolerance.

Only TradingView reported it, and only partially: the syntax error at line 235
(finding 24) halted analysis, so the compiler flagged the `valuewhen` site and
never reached the other two. They were found by scanning for the pattern.

**Fix applied:** all three hoisted to globals evaluated on every bar, with the
gating moved to the outputs. This brings Pine *to* the Python rather than the
reverse — `azimuth/core/signals.py::_entry_gates` already computes the crossover
series across the whole score before applying gates, and
`azimuth/core/rsi_mod.py::divergences` combines fully-computed `valuewhen` series
with elementwise `&`. No Python change was required and none was made.

**Proposed amendment:** widen `03` §6 to "never inside `if` blocks, and never after
a short-circuiting `and`/`or` or inside a ternary branch — assign to a global
variable and use that". Worth adding a CI grep for the pattern, since the compiler
only reports the first instance it reaches.

---

## 24. Continuation lines indented by a multiple of 4 ✅ FIXED

**Where:** `pine/AZIMUTH.pine:236`. **Fixed in commit 6.**

Pine treats a line indented by a multiple of 4 spaces as a **new statement**, and
any other indentation as a continuation of the line above. The `scCol` ternary
wrapped onto a line indented 8 spaces, leaving line 235 ending on a dangling `:` —
`end of line without line continuation` (CE10156).

Every other continuation in the file uses 5 spaces; this was the only one at a
multiple of 4. Re-indented to match, with a comment recording the rule.

Cosmetic in effect — `scCol` is the score plot's colour and touches no `x_*`
export — but it blocked compilation entirely, which is what prevented finding 23's
other two sites from being reported.

---

## Appendix — findings that are *not* being raised

For completeness, three things that look like problems and are not:

- **Divergence pivot lag.** `01` §3.2 and `03` §2 are right: `ta.pivothigh/low`
  confirming `divLb` bars late is lag, not repainting, and the Python side must
  reproduce it rather than remove it. Handled in `primitives.pivot_high/low`.
- **HTF `s[1]`.** `01` §4's repaint contract is correct and costs up to one HTF bar
  of lag. `07` §1 fixing `htf.confirmed_only = true` and forbidding its sweep is the
  right call and is enforced as a schema validator, not a convention.
- **Stop-before-target on same-bar ambiguity.** `04` §7's conservative assumption
  plus a logged ambiguity count is the correct treatment.
