from pathlib import Path
from typing import Optional
import typer
from rich.console import Console

from jnaara.analysis.semantic import SemanticAnalyzer
from jnaara.analysis.validator import AnalysisValidator
from jnaara.belief.manager import BeliefManager
from jnaara.cli.formatters import (
    print_beliefs_table,
    print_conflicts_table,
    print_provenance_tree,
    print_summary_dashboard,
)
from jnaara.config import Settings, get_settings
from jnaara.conflict.detector import ConflictDetector
from jnaara.conflict.resolver import ConflictResolver
from jnaara.db.engine import get_db_engine, get_session_factory, init_db
from jnaara.db.repository import Repository
from jnaara.evaluation.reporter import save_evaluation_report
from jnaara.ingestion.ingestor import FactIngestor
from jnaara.llm.factory import create_providers
from jnaara.llm.mock import MockLLMProvider

app = typer.Typer(
    name="jnaara",
    help="Jnaara: Deterministic belief engine with LLM semantic analysis and provenance tracking.",
    no_args_is_help=True,
)
console = Console()


def get_pipeline(settings: Settings, strategy_override: Optional[str] = None):
    """Construct the end-to-end belief engine pipeline."""
    engine = get_db_engine(settings.db_path)
    init_db(engine)
    session = get_session_factory(engine)()
    repo = Repository(session)

    # Initialize providers: if API keys are not provided, fallback to MockLLMProvider
    has_groq = bool(settings.groq_api_key and settings.groq_api_key.get_secret_value().strip())
    has_google = bool(settings.google_api_key and settings.google_api_key.get_secret_value().strip())

    if (settings.primary_llm == "groq" and not has_groq) or (settings.secondary_llm == "gemini" and not has_google):
        primary = MockLLMProvider("mock-primary")
        secondary = MockLLMProvider("mock-secondary")
    else:
        try:
            primary, secondary = create_providers(settings)
        except Exception:
            primary = MockLLMProvider("mock-primary")
            secondary = MockLLMProvider("mock-secondary")

    analyzer = SemanticAnalyzer(primary, secondary, AnalysisValidator())
    detector = ConflictDetector(repo, analyzer)
    active_strat = strategy_override or settings.default_strategy
    resolver = ConflictResolver(active_strat)
    manager = BeliefManager(repo, analyzer, detector, resolver)

    return repo, manager, resolver, session


@app.command()
def ingest(
    dataset_path: Path = typer.Argument(Path("data/jnaara_memory_facts_dataset.json"), help="Path to facts dataset"),
    sequence: Optional[str] = typer.Option(None, "--sequence", "-s", help="Sequence name (e.g., sequence_1_easy)"),
    strategy: Optional[str] = typer.Option(None, "--strategy", help="Resolution strategy (recency or corroboration)"),
):
    """Ingest facts from dataset, extract claims, detect conflicts, and update beliefs."""
    settings = get_settings()
    repo, manager, resolver, session = get_pipeline(settings, strategy_override=strategy)

    try:
        ingestor = FactIngestor()
        if sequence:
            facts = ingestor.load_sequence(dataset_path, sequence)
            sequences_to_run = [(sequence, facts)]
        else:
            all_seqs = ingestor.load_dataset(dataset_path)
            sequences_to_run = list(all_seqs.items())

        total_processed = 0
        total_skipped = 0
        total_conflicts = 0
        total_claims = 0
        recorded_results = []

        for seq_name, facts in sequences_to_run:
            console.print(f"\n[bold cyan]Processing {seq_name} ({len(facts)} facts) with strategy '{resolver.active_strategy}'...[/bold cyan]")
            for f in facts:
                res = manager.process_fact(f)
                conflicts_in_fact = sum(1 for _, c in res.results if c is not None)
                recorded_results.append({
                    "fact_id": res.fact_id,
                    "content": f.content,
                    "source": f.source,
                    "source_reliability": f.source_reliability,
                    "skipped": res.skipped,
                    "claims": [c.model_dump() for c in res.claims],
                    "decisions": [dec.model_dump() for dec, _ in res.results],
                    "conflicts": [conf.model_dump() for _, conf in res.results if conf is not None],
                })
                if res.skipped:
                    total_skipped += 1
                else:
                    total_processed += 1
                    total_claims += len(res.claims)
                    total_conflicts += conflicts_in_fact
                    status_badge = f"[yellow]{conflicts_in_fact} conflict(s)[/yellow]" if conflicts_in_fact else "[green]OK[/green]"
                    console.print(f"  Fact [bold]{f.id}[/bold]: {status_badge} ({len(res.claims)} claims extracted)")

        console.print(f"\n[bold green][OK] Ingestion Complete![/bold green] Processed: {total_processed}, Skipped: {total_skipped}, Conflicts: {total_conflicts}")

        # Save evaluation report to output/ folder
        try:
            active_beliefs = repo.get_all_beliefs(status="active")
            output_file = save_evaluation_report(
                output_dir=settings.output_dir,
                source_name=dataset_path.name,
                sequence=sequence,
                strategy=resolver.active_strategy,
                summary={
                    "total_submitted": total_processed + total_skipped,
                    "total_processed": total_processed,
                    "total_skipped": total_skipped,
                    "total_claims": total_claims,
                    "total_conflicts": total_conflicts,
                },
                results=recorded_results,
                active_beliefs=[b.model_dump() for b in active_beliefs],
            )
            console.print(f"[bold cyan]Evaluation report saved to:[/bold cyan] {output_file}")
        except Exception as exc:
            console.print(f"[yellow]Notice: Could not save evaluation report: {exc}[/yellow]")
    finally:
        session.close()


@app.command()
def beliefs(
    entity: Optional[str] = typer.Option(None, "--entity", "-e", help="Filter beliefs by entity name"),
):
    """Display active held beliefs."""
    settings = get_settings()
    repo, _, _, session = get_pipeline(settings)
    try:
        if entity:
            beliefs_list = repo.get_beliefs_for_entity(entity)
        else:
            beliefs_list = repo.get_all_beliefs(status="active")

        if not beliefs_list:
            console.print("[yellow]No active beliefs found.[/yellow]")
            return

        print_beliefs_table(beliefs_list, entity_filter=entity)
    finally:
        session.close()


@app.command()
def conflicts(
    entity: Optional[str] = typer.Option(None, "--entity", "-e", help="Filter conflicts by entity name"),
):
    """Display detected contradictions and how they were resolved."""
    settings = get_settings()
    repo, _, _, session = get_pipeline(settings)
    try:
        conflicts_list = repo.get_conflicts(entity=entity)
        if not conflicts_list:
            console.print("[green]No conflicts detected.[/green]")
            return

        print_conflicts_table(conflicts_list, entity_filter=entity)
    finally:
        session.close()


@app.command()
def provenance(
    belief_id: str = typer.Argument(..., help="ID (full or prefix) of the belief to audit"),
):
    """Inspect full provenance, history, and evidence trail for a specific belief."""
    settings = get_settings()
    repo, _, _, session = get_pipeline(settings)
    try:
        # Search by full ID or prefix match
        target_id = belief_id
        all_beliefs = repo.get_all_beliefs()
        matching = [b for b in all_beliefs if b.id.startswith(belief_id)]
        if matching:
            target_id = matching[0].id

        prov = repo.get_provenance_chain(target_id)
        print_provenance_tree(prov)
    except Exception as exc:
        console.print(f"[bold red]Error fetching provenance:[/bold red] {exc}")
    finally:
        session.close()


@app.command()
def strategy(
    name: Optional[str] = typer.Argument(None, help="Name of strategy to switch to ('recency' or 'corroboration')"),
):
    """View or switch the active conflict resolution strategy."""
    resolver = ConflictResolver()
    available = resolver.list_strategies()

    if name:
        try:
            resolver.switch_strategy(name)
            console.print(f"[bold green]Switched active conflict resolution strategy to:[/bold green] [cyan]{resolver.active_strategy}[/cyan]")
        except ValueError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
    else:
        console.print(f"Active Strategy: [bold green]{resolver.active_strategy}[/bold green]")
        console.print(f"Available Strategies: {available}")


@app.command()
def reset(
    force: bool = typer.Option(False, "--force", "-f", help="Bypass confirmation prompt"),
):
    """Reset the database and clear all facts, beliefs, conflicts, and provenance history."""
    if not force:
        confirm = typer.confirm("Are you sure you want to clear the entire belief database?")
        if not confirm:
            console.print("[yellow]Reset cancelled.[/yellow]")
            return

    settings = get_settings()
    repo, _, _, session = get_pipeline(settings)
    try:
        repo.clear_all()
        console.print("[bold green][OK] Belief database cleared successfully.[/bold green]")
    finally:
        session.close()


@app.command()
def summary():
    """Display an executive summary dashboard of current knowledge state."""
    settings = get_settings()
    repo, _, resolver, session = get_pipeline(settings)
    try:
        all_facts = repo.get_all_facts()
        active_beliefs = repo.get_all_beliefs(status="active")
        all_conflicts = repo.get_conflicts()

        stats = {
            "total_facts": len(all_facts),
            "active_beliefs": len(active_beliefs),
            "total_conflicts": len(all_conflicts),
            "active_strategy": resolver.active_strategy,
            "primary_llm": settings.primary_llm,
            "secondary_llm": settings.secondary_llm,
        }
        print_summary_dashboard(stats)
    finally:
        session.close()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host interface to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    reload: bool = typer.Option(True, "--reload", help="Enable auto-reload on code changes"),
):
    """Start the Jnaara FastAPI REST API server."""
    try:
        import uvicorn
    except ImportError:
        console.print("[bold red]Error:[/bold red] uvicorn is not installed. Run 'uv sync --extra api'.")
        raise typer.Exit(1)

    console.print(f"[bold green]Starting Jnaara API server at[/bold green] [cyan]http://{host}:{port}[/cyan]")
    console.print(f"API Docs available at: [cyan]http://{host}:{port}/docs[/cyan]")
    uvicorn.run("jnaara.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
