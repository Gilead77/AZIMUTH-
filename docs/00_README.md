# AZIMUTH 🧭
**Composite signal engine — Pine v6 indicator + Python validation CLI**

Ribbon 🎀 · Bollinger Bands · RSI · Higher-timeframe bias · Cross-asset correlation · Regime gate

---

## What this is

A **bounded-score confluence engine**, not an indicator stack. Every component
emits a score in `[-1, +1]`. A weighted composite in `[-100, +100]` drives a
state machine with hysteresis, a regime gate and a cooldown.

Two artefacts:

| Artefact | Purpose |
|---|---|
| `pine/AZIMUTH.pine` | Live chart signals + webhook alerts on TradingView |
| `azimuth` (Python CLI) | Offline replication, backtest, **and the statistics that decide whether the thing is real** |

## The uncomfortable part, stated up front

Multi-indicator confluence systems have an extremely poor out-of-sample record.
The failure mode is not that the components are wrong — it is that **the
component set, the weights, and the thresholds together give you a parameter
space large enough to fit noise perfectly**. With 5 components × ~20 tunable
parameters you can hit any equity curve you like on any historical sample.

This project is therefore built **validation-first**. The Python CLI's job is to
try to kill AZIMUTH, and only report a result after:

1. Pre-registration of the hypothesis (`09_PREREGISTRATION.md`)
2. Purged, embargoed walk-forward (never a single in-sample fit)
3. Realistic costs (spread + commission + slippage, swept)
4. A **permutation null** — same machinery on bar-shuffled data
5. **Deflated Sharpe** correcting for the number of configurations tried
6. Benchmarks: buy & hold, and random entries matched on trade count and holding period

If AZIMUTH does not beat those, the correct output is a documented null result —
exactly as MERIDIAN produced. A clean null is a successful run of this project.

## Repo layout

```
azimuth/
├── pine/
│   ├── AZIMUTH.pine              # indicator (ships working today)
│   ├── AZIMUTH_strategy.pine     # TV strategy wrapper (smoke test only)
│   └── azimuth_core.pine         # shared library (to be extracted)
├── azimuth/                      # Python package
│   ├── cli.py
│   ├── data/ core/ backtest/ validate/ report/
├── config/default.yaml
├── tests/
├── docs/                         # you are here
└── CLAUDE.md
```

## Docs index

| File | Contents |
|---|---|
| `01_SPEC_COMPONENTS.md` | Exact maths for every component score |
| `02_SPEC_SCORING.md` | Composite, regime polarity, state machine |
| `03_SPEC_PINE.md` | Pine implementation rules, repaint contract |
| `04_SPEC_PYTHON_CLI.md` | CLI architecture and commands |
| `05_SPEC_VALIDATION.md` | The statistics. Read this one twice. |
| `06_PARITY_TESTS.md` | Pine ↔ Python agreement harness |
| `07_PARAMETERS.md` | Defaults, rationale, sweep ranges |
| `08_ALERTS.md` | Webhook JSON schema |
| `09_PREREGISTRATION.md` | Fill this in **before** running the sweep |
| `10_ROADMAP.md` | Build order and milestones |
| `11_FINDINGS.md` | Findings raised against 00–10, awaiting adjudication. **Not authoritative** |

## Quickstart (Pine)

1. TradingView → Pine Editor → paste `pine/AZIMUTH.pine` → Save → Add to chart.
2. Set HTF 1 / HTF 2 to roughly 4× and 24× your chart timeframe.
3. Set the correlation references to things that actually drive your instrument
   (see `07_PARAMETERS.md` §5 — the defaults are placeholders).
4. Do **not** trade it. Export the data window to CSV and go to the Python harness.

> Research tool. Not financial advice. Nothing here is a recommendation to trade
> any instrument.
