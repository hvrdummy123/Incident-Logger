"""TraceIQ CLI entrypoint."""

from __future__ import annotations

import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from traceiq import __version__

app = typer.Typer(
    name="traceiq",
    help="TraceIQ — investigate incidents with cited evidence.",
    no_args_is_help=True,
)
console = Console(stderr=True)


@app.callback()
def _main() -> None:
    pass


@app.command()
def version() -> None:
    """Print TraceIQ version."""
    typer.echo(__version__)


@app.command()
def doctor(
    database_url: Annotated[
        str | None,
        typer.Option(help="Override TRACEIQ_DATABASE_URL for the check"),
    ] = None,
) -> None:
    """Check DB, model config, egress mode, disk, and versions."""
    from pathlib import Path

    from traceiq.config import Settings, get_settings

    settings = get_settings() if database_url is None else Settings(database_url=database_url)
    rows: list[tuple[str, str, str]] = []
    ok = True

    rows.append(("traceiq", __version__, "ok"))
    rows.append(("python", f"{sys.version_info.major}.{sys.version_info.minor}", "ok"))

    try:
        provider, model_id = settings.parse_model()
        rows.append(("model", f"{provider}:{model_id}", "ok"))
    except ValueError as e:
        rows.append(("model", str(e), "fail"))
        ok = False

    if settings.no_external_llm:
        egress = "blocked (NO_EXTERNAL_LLM)"
    else:
        egress = "external allowed (redacted)"
    rows.append(("egress", egress, "ok"))

    data_dir = Path(settings.data_dir)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".doctor_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        rows.append(("data_dir", str(data_dir.resolve()), "ok"))
    except OSError as e:
        rows.append(("data_dir", str(e), "fail"))
        ok = False

    db_status = "skip"
    db_detail = settings.database_url.split("@")[-1] if "@" in settings.database_url else "(set)"
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
        rows.append(("postgres", db_detail, db_status))
    except Exception as e:  # noqa: BLE001 — doctor must never crash
        # M0/M1: Postgres may not be up yet; report clearly, exit non-zero only if required later.
        rows.append(("postgres", f"{db_detail} — {e.__class__.__name__}: {e}", "warn"))

    table = Table(title="traceiq doctor")
    table.add_column("check")
    table.add_column("detail")
    table.add_column("status")
    for name, detail, status in rows:
        table.add_row(name, detail, status)
    console.print(table)

    if not ok:
        raise typer.Exit(code=1)
    if db_status == "ok":
        console.print("[green]verdict: ready for local work[/green]")
    else:
        console.print("[yellow]verdict: code ok; start Postgres for full stack[/yellow]")


# Placeholders so --help documents the eventual surface (wired in later milestones).
demo_app = typer.Typer(help="Demo incident bundles")
app.add_typer(demo_app, name="demo")


@demo_app.command("list")
def demo_list() -> None:
    """List shipped demo incidents (available after M4)."""
    console.print(
        "Demos not generated yet (milestone M4). "
        "Expected: incident-1-bad-deploy, incident-2-db-pool, "
        "incident-3-cache-stampede."
    )


if __name__ == "__main__":
    app()
