# Kickoff prompt for Claude Code

> Copy everything below the line into Claude Code from the repo root, after
> placing the `docs/`, `pine/` and `CLAUDE.md` files in it.

---

I'm building **AZIMUTH**, a composite trading-signal engine: a Pine v6
TradingView indicator plus a Python validation CLI. The full specification is in
`docs/` (files `00_README.md` through `10_ROADMAP.md`) and the project rules are
in `CLAUDE.md`. **Read all of them before writing any code** — they are
authoritative and I've already made the design decisions deliberately.

The working Pine indicator is already at `pine/AZIMUTH.pine`.

## Framing, so you optimise for the right thing

The deliverable is **a defensible verdict on whether this signal has an edge** —
not a profitable-looking backtest. My prior is that it doesn't; most confluence
systems don't survive honest validation. Your job is to build the instrument that
tries hardest to kill it. A clean, well-documented null result is a successful
outcome and I want you to treat it as one. If at any point you find yourself
tempted to loosen a criterion, add a component, or extend the sample to make
results look better, stop and tell me instead.

## Task 1 — Scaffold (do this first, then pause for review)

Create the Python package per `docs/04_SPEC_PYTHON_CLI.md` §3:
- `uv`-managed project, Python 3.11+, `pyproject.toml`
- Full directory tree with module stubs and docstrings referencing the spec section each implements
- `pydantic` config schema + `config/default.yaml` using the exact key names in `docs/07_PARAMETERS.md` §1
- `typer` CLI with all commands registered as not-yet-implemented stubs
- GitHub Actions CI: `ruff`, `mypy --strict` on `core/` and `validate/`, `pytest`
- `.gitignore`, `runs/N_trials.txt` initialised to 0

Then stop and show me the tree.

## Task 2 — Primitives and the lookahead test

Implement `azimuth/core/primitives.py` with **Pine-exact** `ema`, `rma`, `rsi`,
`stdev`, `atr`, `percentrank`, `correlation`, `dmi`, `pivot_high`, `pivot_low`.

`docs/06_PARITY_TESTS.md` §3 lists the specific ways naive pandas implementations
differ from Pine. Handle every one of them, with a named regression test each.

Write `tests/test_lookahead.py` **before** anything else that consumes these: a
`hypothesis` property test asserting that truncating any input series at bar *t*
never changes any computed value at bars ≤ *t*. This is the most important test
in the repo.

Then stop and show me the test results.

## Task 3 onwards

Follow `docs/10_ROADMAP.md` milestones M1 → M4 in order. **Pause at each
milestone exit criterion** for my review rather than running ahead.

Do not compute or report a single performance metric until `azimuth parity`
passes at 1e-6 against a Pine fixture export. I'll provide the fixture CSV after
I compile-check the indicator.

## Ground rules (also in CLAUDE.md)

- No lookahead, anywhere, ever.
- No `pandas_ta`, no `TA-Lib`.
- The pre-registration gate in `azimuth validate` is a hard error with no bypass flag.
- `runs/N_trials.txt` accumulates across the whole project lifetime and is never reset.
- Tests ship in the same commit as the code they cover.

## First thing I want from you

Before writing any code: read the docs and give me a short critique. Specifically —
where do you think the design is weakest, which of the five components do you
expect to fail the ablation test in `docs/02_SPEC_SCORING.md` §5, and is there
anything in the validation protocol that I've got wrong or that has a hole in it?
I'd rather find the flaws now than after M4.
