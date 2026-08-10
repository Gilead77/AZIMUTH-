"""AZIMUTH command-line interface.

Implements the command surface in ``docs/04_SPEC_PYTHON_CLI.md`` section 4.

The CLI is not a trading bot. It is the instrument that decides whether AZIMUTH is
real (docs/04 section 1). Commands are registered here as stubs; each names the
roadmap milestone (``docs/10_ROADMAP.md``) that implements it.

One thing is NOT a stub: the pre-registration gate on ``azimuth validate``. It is
wired to the real check in ``azimuth/validate/gate.py`` from the first commit,
because a guard rail that arrives later is a guard rail that was absent exactly
when it mattered.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, NoReturn

import pandas as pd
import typer
from rich.console import Console

from azimuth.validate.gate import PreRegistrationError, assert_preregistration_valid

app = typer.Typer(
    name="azimuth",
    help=(
        "AZIMUTH — composite signal engine and validation harness.\n\n"
        "Research tool. Not financial advice. No performance number produced by this "
        "CLI is meaningful until `azimuth parity` passes at 1e-6 against a Pine "
        "fixture export (CLAUDE.md rule 2)."
    ),
    no_args_is_help=True,
    add_completion=False,
)

console = Console()
err_console = Console(stderr=True)


def _not_implemented(command: str, milestone: str, detail: str = "") -> NoReturn:
    """Exit non-zero for an unimplemented command.

    Non-zero rather than a friendly no-op: a scripted pipeline must not mistake a
    stub for a successful run that produced no output.
    """
    err_console.print(f"[bold red]not implemented[/] — `azimuth {command}` lands in {milestone}.")
    if detail:
        err_console.print(f"  {detail}")
    raise typer.Exit(code=2)


# ── global options ──────────────────────────────────────────────────────────────

ConfigOpt = Annotated[
    Path | None,
    typer.Option("--config", help="Config YAML. Defaults to the packaged config/default.yaml."),
]
CacheDirOpt = Annotated[
    Path, typer.Option("--cache-dir", help="Parquet cache root, keyed by (symbol, tf, start, end).")
]
SeedOpt = Annotated[int, typer.Option("--seed", help="RNG seed. Recorded in the run manifest.")]
NoCacheOpt = Annotated[bool, typer.Option("--no-cache", help="Bypass the parquet cache.")]


@app.callback()
def main(
    log_level: Annotated[
        str, typer.Option("--log-level", help="DEBUG | INFO | WARNING | ERROR")
    ] = "INFO",
) -> None:
    """Global options (docs/04_SPEC_PYTHON_CLI.md section 4)."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


# ── data ────────────────────────────────────────────────────────────────────────


@app.command()
def fetch(
    symbol: Annotated[str, typer.Option("--symbol", help="e.g. BTC-USD")],
    tf: Annotated[str, typer.Option("--tf", help="e.g. 4h")],
    start: Annotated[str, typer.Option("--start", help="ISO date, e.g. 2018-01-01")] = "2018-01-01",
    source: Annotated[str, typer.Option("--source", help="yfinance | ccxt | csv")] = "yfinance",
    cache_dir: CacheDirOpt = Path("cache"),
    no_cache: NoCacheOpt = False,
) -> None:
    """Fetch OHLCV into the canonical frame (docs/04 section 5). [M1]"""
    _not_implemented("fetch", "M1", "azimuth/data/loaders.py")


@app.command()
def signals(
    symbol: Annotated[str, typer.Option("--symbol")],
    tf: Annotated[str, typer.Option("--tf")],
    last: Annotated[int, typer.Option("--last", help="Show the most recent N bars.")] = 20,
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
    source: Annotated[str, typer.Option("--source", help="yfinance | ccxt | csv")] = "yfinance",
    csv: Annotated[Path | None, typer.Option("--csv", help="Local CSV when --source csv.")] = None,
    start: Annotated[str, typer.Option("--start")] = "2018-01-01",
    config: ConfigOpt = None,
) -> None:
    """Compute the composite score and state machine offline. [M1]

    Signal values only. NO performance metric is produced here and none may be
    until parity passes (CLAUDE.md rule 2).
    """
    import json as json_lib

    from rich.table import Table

    from azimuth.config.schema import load_config
    from azimuth.core.pipeline import compute_frame
    from azimuth.data import loaders

    settings = load_config(config)

    if source == "csv":
        if csv is None:
            err_console.print("[bold red]--csv is required with --source csv[/]")
            raise typer.Exit(code=2)
        df = loaders.load_csv(csv, symbol, tf)
    elif source == "ccxt":
        df = loaders.load_ccxt(symbol, tf, start)
    else:
        df = loaders.load_yfinance(symbol, tf, start)

    frame = compute_frame(df, settings)
    columns = ["x_ribbon", "x_bb", "x_rsi", "x_htf", "x_corr", "score", "x_state"]
    tail = frame[columns].tail(last)

    if json_out:
        payload = tail.reset_index().to_dict(orient="records")
        console.print_json(json_lib.dumps(payload, default=str))
        return

    table = Table(title=f"{symbol} {tf} — last {last} bars", title_style="bold")
    table.add_column("time")
    for column in columns:
        table.add_column(column, justify="right")

    for timestamp, row in tail.iterrows():
        table.add_row(
            str(timestamp),
            *(
                "—" if pd.isna(row[c]) else (f"{row[c]:.0f}" if c == "x_state" else f"{row[c]:.3f}")
                for c in columns
            ),
        )
    console.print(table)
    console.print(
        "[dim]Signal values only. No performance metric exists until `azimuth parity` "
        "passes at 1e-6 (CLAUDE.md rule 2).[/]"
    )


# ── parity: the gate on every performance number ────────────────────────────────


@app.command()
def parity(
    pine: Annotated[Path, typer.Option("--pine", help="Pine 'Export chart data' CSV.")],
    tol: Annotated[
        float | None,
        typer.Option("--tol", help="Override every per-series tolerance with one value."),
    ] = None,
    config: ConfigOpt = None,
) -> None:
    """Assert Python matches the Pine fixture (docs/06_PARITY_TESTS.md). [M1]

    THE GATE. Until it passes, any backtest describes a system that is not the one
    on the chart, and its metrics are not about AZIMUTH (CLAUDE.md rule 2).

    Exits non-zero on any mismatch. With no ``--tol`` the per-series tolerances in
    docs/06 section 2 apply, which is how the gate should normally run; passing
    ``--tol`` loosens every series at once and is for diagnosis only.
    """
    from rich.table import Table

    from azimuth.config.schema import load_config
    from azimuth.validate.parity import run_parity

    report = run_parity(pine, load_config(config), tol=tol)

    table = Table(title=f"parity — {pine.name}", title_style="bold")
    table.add_column("series")
    table.add_column("max |delta|", justify="right")
    table.add_column("tolerance", justify="right")
    table.add_column("bars", justify="right")
    table.add_column("verdict")

    for result in report.results:
        table.add_row(
            result.series,
            "—" if result.series == "signal_bars" else f"{result.max_abs_diff:.3e}",
            "exact" if result.tolerance == 0.0 else f"{result.tolerance:.0e}",
            str(result.n_compared),
            "[green]PASS[/]" if result.passed else f"[bold red]FAIL[/] {result.detail}",
        )

    console.print(table)
    console.print(
        f"{report.n_compared} bars compared after a {report.n_bars - report.n_compared}-bar burn-in"
    )

    if report.missing:
        err_console.print(
            f"[yellow]not compared[/] (absent from the export): {', '.join(report.missing)}"
        )

    if not report.passed:
        failed = [r.series for r in report.results if not r.passed]
        err_console.print(f"\n[bold red]PARITY FAILED[/] — {', '.join(failed)}")
        err_console.print(
            "No performance metric may be computed until this passes (CLAUDE.md rule 2). "
            "docs/06 section 3 lists the usual causes; for x_ribbon suspect ATR/RMA "
            "seeding before the EMA."
        )
        raise typer.Exit(code=1)

    console.print("\n[bold green]PARITY PASSED[/] — Python matches the chart.")


# ── backtest ────────────────────────────────────────────────────────────────────


@app.command()
def backtest(
    symbol: Annotated[str, typer.Option("--symbol")],
    tf: Annotated[str, typer.Option("--tf")],
    config: ConfigOpt = None,
    seed: SeedOpt = 0,
) -> None:
    """Next-bar-open fill engine → trade ledger + metrics (docs/04 section 7). [M2]

    Increments runs/N_trials.txt on every evaluation that produces a Sharpe
    (CLAUDE.md rule 4; docs/11_FINDINGS.md finding 6).
    """
    _not_implemented("backtest", "M2", "azimuth/backtest/engine.py")


@app.command()
def sweep(
    grid: Annotated[Path, typer.Option("--grid", help="Grid YAML (docs/07 section 2 staging).")],
    out: Annotated[Path, typer.Option("--out", help="Run directory.")],
    workers: Annotated[int, typer.Option("--workers")] = 8,
    seed: SeedOpt = 0,
) -> None:
    """Staged parameter sweep on IN-SAMPLE data only (docs/07 section 2). [M3]

    Writes the pre-registration path, its SHA-256 and the recording time into the
    run manifest before the first configuration is evaluated.
    """
    _not_implemented("sweep", "M3", "docs/07_PARAMETERS.md section 2 — staged, not a full grid")


# ── validation ──────────────────────────────────────────────────────────────────


@app.command()
def validate(
    run: Annotated[Path, typer.Option("--run", help="Run directory containing manifest.json.")],
    preregistration: Annotated[
        Path, typer.Option("--preregistration", help="Pre-registration markdown.")
    ] = Path("docs/09_PREREGISTRATION.md"),
) -> None:
    """Walk-forward, nulls, multiple-testing correction (docs/05). [M3]

    The pre-registration gate below is live from the first commit and has no
    bypass flag (CLAUDE.md rule 3). Do not add one.
    """
    try:
        sha = assert_preregistration_valid(preregistration, run / "manifest.json")
    except PreRegistrationError as exc:
        err_console.print("[bold red]PRE-REGISTRATION GATE: REFUSED[/]\n")
        err_console.print(str(exc))
        raise typer.Exit(code=3) from exc

    console.print(f"[green]pre-registration gate passed[/] — sha256 {sha[:16]}…")
    _not_implemented("validate", "M3", "azimuth/validate/walkforward.py and siblings")


@app.command()
def ablate(
    symbol: Annotated[str, typer.Option("--symbol")],
    tf: Annotated[str, typer.Option("--tf")],
    config: ConfigOpt = None,
) -> None:
    """Zero each component weight in turn (docs/02 section 5). [M3]

    Every ablation is a configuration evaluated, so each one counts toward N.
    """
    _not_implemented("ablate", "M3", "docs/02_SPEC_SCORING.md section 5")


# ── output ──────────────────────────────────────────────────────────────────────


@app.command()
def report(
    run: Annotated[Path, typer.Option("--run")],
    out: Annotated[Path, typer.Option("--out", help="Self-contained HTML.")],
) -> None:
    """Render a run as a single self-contained HTML report. [M3]"""
    _not_implemented("report", "M3", "azimuth/report/html.py")


@app.command()
def watch(
    symbols: Annotated[str, typer.Option("--symbols", help="Comma-separated.")],
    tf: Annotated[str, typer.Option("--tf")],
    sink: Annotated[
        str, typer.Option("--sink", help="stdout | webhook:// | ntfy:// | file://")
    ] = "stdout",
    config: ConfigOpt = None,
) -> None:
    """Poll, recompute, emit the docs/08 alert payload. [M5 — conditional]

    Notifications only. No broker execution, no order routing (docs/08 section 5).
    M5 is gated on M4 passing all ten criteria in docs/05 section 6.
    """
    _not_implemented("watch", "M5", "conditional on M4 — docs/10_ROADMAP.md")


if __name__ == "__main__":  # pragma: no cover
    app()
