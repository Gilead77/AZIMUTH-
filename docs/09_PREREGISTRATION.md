# 09 — Pre-Registration ✍️

> Fill in, commit, and record the SHA-256 **before** running any sweep.
> `azimuth validate` will refuse to run otherwise.
> Do not edit after results are seen. Start a new file instead, and increment N.

---

**Registration ID:** AZIMUTH-PR-001
**Date:** ____________
**Author:** Harry
**Commit SHA at registration:** ____________

---

## 1. Hypothesis

> State it falsifiably. "AZIMUTH works" is not a hypothesis.

*Example form:* On `<instrument>` at `<timeframe>` over `<period>`, the AZIMUTH
composite score, with the state machine and gates described in
`02_SPEC_SCORING.md`, generates entry signals whose subsequent N-bar returns have
a positive expectancy net of 15 bps round-trip costs, exceeding a random-entry
benchmark matched on trade count and holding period at the 95th percentile.

**H₀:** No such expectancy exists; observed performance is consistent with chance.

**H₁:** ____________________________________________

## 2. Data

| Field | Value |
|---|---|
| Primary instrument | |
| Timeframe | |
| Full sample period | |
| In-sample (50%) | |
| Walk-forward (30%) | |
| Holdout (20%, untouched) | |
| Cross-instrument holdouts | |
| Data source + fetch date | |
| Data SHA-256 | |

## 3. Parameters to be swept

| Stage | Parameters | Count |
|---|---|---|
| 1 structure | | |
| 2 signal | | |
| 3 risk | | |
| 4 weights | | |
| **Cumulative N (this registration)** | | |
| **Cumulative N (project lifetime)** | | |

## 4. Primary metric

Metric: ____________ (one only — pre-committed)
Secondary (reported, not decisive): ____________

## 5. Acceptance criteria

☐ Inherit all ten criteria from `05_SPEC_VALIDATION.md` §6 unchanged
☐ Modified (state deviations and justification below):

____________________________________________

## 6. Costs

Optimistic / realistic / pessimistic (bps round-trip): ____ / ____ / ____
Required break-even multiple: ≥ 2×

## 7. Null models

☐ IID return shuffle (1,000 surrogates)
☐ Block bootstrap, block = 20 (1,000)
☐ Stationary bootstrap, Politis–Romano (1,000)
☐ Random-entry matched benchmark
☐ Buy & hold, raw and vol-matched

## 8. Stopping rule

Analysis stops when the pre-registered stages complete. **No additional
configurations, components, or instruments may be added after seeing results
under this registration.** Anything further requires AZIMUTH-PR-002 and resets
the interpretation.

## 9. Commitment to publication

☐ I commit to writing up the result in `results/` regardless of outcome,
  including a null result.

**Signature / commit:** ____________
**SHA-256 of this file at registration:** ____________
