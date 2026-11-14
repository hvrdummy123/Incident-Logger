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


@app.command("ingest")
def ingest_cmd(
    paths: Annotated[list[str], typer.Argument(help="Log files to ingest")],
    format: Annotated[
        str | None,
        typer.Option("--format", help="Force format (jsonl|logfmt|nginx|cri|syslog|plain)"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--no-dry-run", help="Parse only; no write (default: dry-run)"),
    ] = True,
    workspace_id: Annotated[
        str | None,
        typer.Option("--workspace", help="Workspace id (required unless --dry-run)"),
    ] = None,
) -> None:
    """Ingest log files. Default is --dry-run (parse report only)."""
    import json
    from pathlib import Path

    from rich import print_json

    from traceiq.config import get_settings
    from traceiq.ids import new_ulid
    from traceiq.ingest.pipeline import ingest_file

    settings = get_settings()
    if not dry_run and not workspace_id:
        console.print("[red]--workspace is required when not using --dry-run[/red]")
        raise typer.Exit(2)

    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            console.print(f"[red]not a file: {path}[/red]")
            raise typer.Exit(2)
        result = ingest_file(
            path,
            fmt=format,
            dry_run=dry_run,
            data_dir=Path(settings.data_dir),
            workspace_id=workspace_id,
            dataset_id=None if dry_run else new_ulid(),
        )
        console.print(
            f"[bold]{path.name}[/bold] format={result.report.format} "
            f"confidence={result.report.detect_confidence:.2f}"
        )
        print_json(json.dumps(result.report.to_dict()))
        if result.dataset_path:
            console.print(f"wrote dataset → {result.dataset_path}")


@app.command("audit")
def audit_verify(
    workspace_id: Annotated[str, typer.Argument(help="Workspace to verify")],
) -> None:
    """Verify the hash-chained audit log for a workspace."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from traceiq.audit.chain import verify_chain
    from traceiq.config import get_settings

    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session = sessionmaker(bind=engine)()
    try:
        from sqlalchemy import text

        session.execute(
            text("SELECT set_config('app.workspace_id', :wid, true)"),
            {"wid": workspace_id},
        )
        result = verify_chain(session, workspace_id)
    finally:
        session.close()
    if result.ok:
        console.print(f"[green]audit chain ok[/green] ({result.checked} records)")
    else:
        console.print(
            f"[red]audit chain broken[/red] at seq={result.first_break_seq}: {result.reason}"
        )
        raise typer.Exit(1)


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
