import time
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
from rich.table import Table
from jnaara.db.repository import Repository
from jnaara.evaluation import (
    EvaluationDatasetLoader,
    EvaluatorEngine,
    save_markdown_report,
)
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
    delay: Optional[float] = typer.Option(None, "--delay", "-d", help="Delay in seconds between facts to respect LLM rate limits"),
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

        # Determine effective delay
        is_mock = isinstance(manager.analyzer.primary, MockLLMProvider)
        effective_delay = 0.0 if is_mock else (delay if delay is not None else settings.fact_delay_seconds)

        total_processed = 0
        total_skipped = 0
        total_conflicts = 0
        total_claims = 0
        recorded_results = []

        for seq_name, facts in sequences_to_run:
            console.print(f"\n[bold cyan]Processing {seq_name} ({len(facts)} facts) with strategy '{resolver.active_strategy}' (delay: {effective_delay:.1f}s)...[/bold cyan]")
            for idx, f in enumerate(facts):
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

                # Sleep between facts to comply with LLM rate limits
                if effective_delay > 0 and idx < len(facts) - 1:
                    time.sleep(effective_delay)

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


@app.command(name="eval")
def evaluate(
    split: str = typer.Option("test", "--split", "-s", help="Dataset split to evaluate ('dev', 'val', 'test')"),
    dataset: Optional[Path] = typer.Option(None, "--dataset", "-d", help="Custom evaluation dataset path"),
    provider: str = typer.Option("mock", "--provider", "-p", help="Evaluator provider ('mock' for deterministic offline, 'live' or 'groq' for live LLM)"),
    output: Path = typer.Option(Path("docs/evaluation.md"), "--output", "-o", help="Path to write markdown evaluation report"),
    json_output: Optional[Path] = typer.Option(None, "--json-output", help="Optional path to write raw JSON evaluation payload"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Display full example-by-example traces"),
):
    """Run independent evaluation against labeled benchmarks and generate performance & failure reports."""
    settings = get_settings()

    console.print(f"\n[bold cyan]=== Jnaara Independent Evaluation Engine ===[/bold cyan]")
    console.print(f"Target Split: [bold yellow]{split}[/bold yellow] | Provider: [bold cyan]{provider}[/bold cyan] | Dataset: {dataset or 'default split'}")

    try:
        examples = EvaluationDatasetLoader.load_split(split=split, custom_path=dataset)
        meta = EvaluationDatasetLoader.get_dataset_metadata(split=split, custom_path=dataset)
    except Exception as exc:
        console.print(f"[bold red]Error loading evaluation dataset:[/bold red] {exc}")
        raise typer.Exit(1)

    console.print(f"Loaded [bold green]{len(examples)}[/bold green] evaluation examples across 15 categories.")
    if meta.get("synthetic"):
        console.print("[dim italic]Notice: Running against synthetic benchmark dataset (not real-world telemetry).[/dim italic]")

    # Initialize evaluator provider
    has_groq = bool(settings.groq_api_key and settings.groq_api_key.get_secret_value().strip())
    has_google = bool(settings.google_api_key and settings.google_api_key.get_secret_value().strip())

    if provider.lower() in ("live", "groq", "gemini"):
        if not (has_groq or has_google):
            console.print("[yellow]Warning: Live API keys not found in environment; falling back to MockLLMProvider.[/yellow]")
            p_factory = lambda: MockLLMProvider("eval-primary")
            s_factory = lambda: MockLLMProvider("eval-secondary")
            prov_label = "MockLLMProvider (Deterministic Offline)"
        else:
            p_factory = lambda: create_providers(settings)[0]
            s_factory = lambda: create_providers(settings)[1]
            prov_label = f"Live LLM ({settings.primary_llm})"
    else:
        p_factory = lambda: MockLLMProvider("eval-primary")
        s_factory = lambda: MockLLMProvider("eval-secondary")
        prov_label = "MockLLMProvider (Deterministic Offline)"

    evaluator = EvaluatorEngine(
        primary_provider_factory=p_factory,
        secondary_provider_factory=s_factory,
    )

    console.print(f"Running evaluation with provider: [cyan]{prov_label}[/cyan]...")
    payload = evaluator.evaluate_split(
        examples=examples,
        dataset_name=meta.get("dataset_name", "Jnaara Benchmark"),
        split_name=split,
        provider_name=prov_label,
    )

    m = payload.metrics
    cm = m.confusion_matrix

    # Scorecard Table
    score_table = Table(title=f"Evaluation Performance Scorecard ({split.upper()} Split)", header_style="bold magenta")
    score_table.add_column("Metric", style="cyan", justify="left")
    score_table.add_column("Score", style="bold green", justify="right")
    score_table.add_column("Count / Details", style="yellow", justify="left")

    score_table.add_row("Accuracy", f"{m.accuracy * 100:.1f}%", f"{sum(1 for r in payload.results if r.is_correct)} / {m.total_examples} total correct")
    score_table.add_row("Precision", f"{m.precision * 100:.1f}%", f"TP: {m.tp} / (TP: {m.tp} + FP: {m.fp})")
    score_table.add_row("Recall (Sensitivity)", f"{m.recall * 100:.1f}%", f"TP: {m.tp} / (TP: {m.tp} + FN: {m.fn})")
    score_table.add_row("F1 Score", f"{m.f1 * 100:.1f}%", "Harmonic mean of precision & recall")
    score_table.add_row("Specificity", f"{m.specificity * 100:.1f}%", f"TN: {m.tn} / (TN: {m.tn} + FP: {m.fp})")
    score_table.add_row("False Positives (FP)", f"{m.fp}", "False alarms on non-contradictions")
    score_table.add_row("False Negatives (FN)", f"{m.fn}", "Missed contradictions")
    score_table.add_row("Abstention Accuracy", f"{m.abstention_accuracy * 100:.1f}%", f"{cm.correct_uncertain} / {m.abstention_count} rumors correctly held")

    console.print()
    console.print(score_table)

    # Confusion Matrix Table
    cm_table = Table(title="Confusion Matrix (Predicted vs Actual)", header_style="bold blue")
    cm_table.add_column("Actual / Predicted", style="bold", justify="left")
    cm_table.add_column("Contradiction", justify="center")
    cm_table.add_column("No Contradiction", justify="center")
    cm_table.add_column("Uncertain / Abstain", justify="center")

    cm_table.add_row("Contradiction", f"[bold green]{cm.tp}[/bold green] (TP)", f"[bold red]{cm.fn}[/bold red] (FN)", f"[yellow]{cm.contradiction_as_uncertain}[/yellow]")
    cm_table.add_row("No Contradiction", f"[bold red]{cm.fp}[/bold red] (FP)", f"[bold green]{cm.tn}[/bold green] (TN)", f"[yellow]{cm.no_contradiction_as_uncertain}[/yellow]")
    cm_table.add_row("Uncertain (Rumor)", f"[bold red]{cm.uncertain_as_contradiction}[/bold red]", f"[yellow]{cm.uncertain_as_no_contradiction}[/yellow]", f"[bold green]{cm.correct_uncertain}[/bold green]")

    console.print()
    console.print(cm_table)

    # Failure Mode Summary
    if payload.failures:
        console.print(f"\n[bold red]Visible Failure Analysis ({len(payload.failures)} failures detected):[/bold red]")
        fail_table = Table(header_style="bold red")
        fail_table.add_column("ID", style="bold", width=10)
        fail_table.add_column("Category", width=22)
        fail_table.add_column("GT", width=12)
        fail_table.add_column("Pred", width=12)
        fail_table.add_column("Failure Mode", width=25)
        fail_table.add_column("Diagnosis", width=40)

        for f in payload.failures[:8]:
            fail_table.add_row(
                f.example_id,
                f.category,
                f.ground_truth,
                f.predicted,
                f.failure_category,
                f.explanation[:38] + "..." if len(f.explanation) > 38 else f.explanation,
            )
        console.print(fail_table)

    # Write Markdown Report
    try:
        saved_md = save_markdown_report(payload, output)
        console.print(f"\n[bold green][OK] Evaluation report saved to:[/bold green] [cyan]{saved_md}[/cyan]")
    except Exception as exc:
        console.print(f"[yellow]Warning: Could not save markdown report: {exc}[/yellow]")

    # Write JSON payload if requested
    if json_output:
        try:
            json_output.parent.mkdir(parents=True, exist_ok=True)
            with open(json_output, "w", encoding="utf-8") as jf:
                jf.write(payload.model_dump_json(indent=2))
            console.print(f"[bold green][OK] JSON payload saved to:[/bold green] [cyan]{json_output}[/cyan]")
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not save JSON output: {exc}[/yellow]")

    console.print("[dim]Evaluation run complete. Results are reproducible and independently auditable.[/dim]\n")


if __name__ == "__main__":
    app()
