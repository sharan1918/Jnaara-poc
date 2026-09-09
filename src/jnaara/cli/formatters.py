from typing import Any
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from jnaara.models.domain import Belief, Conflict, Fact, ProvenanceChain

console = Console()


def print_beliefs_table(beliefs: list[Belief], entity_filter: str | None = None) -> None:
    """Render a Rich table of held beliefs."""
    title = f"Current Beliefs ({entity_filter})" if entity_filter else "Current Active Beliefs"
    table = Table(title=title, box=ROUNDED, header_style="bold cyan")
    table.add_column("Belief ID", style="dim", width=10)
    table.add_column("Entity", style="bold green", min_width=18)
    table.add_column("Attribute", style="yellow", min_width=18)
    table.add_column("Value", style="bold white", min_width=18)
    table.add_column("Conf.", justify="right", width=6)
    table.add_column("Ver.", justify="center", width=5)
    table.add_column("Supporting", style="cyan", min_width=10)
    table.add_column("Contradicting", style="red", min_width=10)
    table.add_column("Status", justify="center", width=8)

    for b in beliefs:
        status_style = "green" if b.status == "active" else ("yellow" if b.status == "disputed" else "dim")
        table.add_row(
            b.id[:8],
            b.entity,
            b.attribute,
            b.value,
            f"{b.confidence:.2f}",
            str(b.version),
            ", ".join(b.supporting_fact_ids),
            ", ".join(b.contradicting_fact_ids) if b.contradicting_fact_ids else "-",
            f"[{status_style}]{b.status}[/{status_style}]",
        )

    console.print(table)


def print_conflicts_table(conflicts: list[Conflict], entity_filter: str | None = None) -> None:
    """Render a Rich table of detected contradictions and their resolutions."""
    title = f"Detected Conflicts & Resolutions ({entity_filter})" if entity_filter else "Detected Conflicts & Resolutions"
    table = Table(title=title, box=ROUNDED, header_style="bold magenta")
    table.add_column("Conflict ID", style="dim", width=10)
    table.add_column("Type", style="cyan", width=12)
    table.add_column("Entity", style="bold green", min_width=15)
    table.add_column("Attribute", style="yellow", min_width=15)
    table.add_column("Sev.", justify="center", width=6)
    table.add_column("Winner", style="bold white", width=14)
    table.add_column("Strategy", style="blue", width=14)
    table.add_column("Rationale", style="italic", min_width=25)

    for c in conflicts:
        sev_color = "red" if c.severity == "high" else ("yellow" if c.severity == "medium" else "cyan")
        winner = c.resolution.winner if c.resolution else "Unresolved"
        strategy = c.resolution.strategy_used if c.resolution else "-"
        rationale = c.resolution.rationale if c.resolution else c.description

        table.add_row(
            c.id[:8],
            c.conflict_type,
            c.entity,
            c.attribute,
            f"[{sev_color}]{c.severity.upper()}[/{sev_color}]",
            winner,
            strategy,
            rationale[:90] + "..." if len(rationale) > 90 else rationale,
        )

    console.print(table)


def print_provenance_tree(prov: ProvenanceChain) -> None:
    """Render a full hierarchical Rich tree illustrating the belief's audit trail."""
    b = prov.belief
    root = Tree(
        f"[bold green]Belief {b.id[:8]}[/bold green]: [white]{b.entity} -> {b.attribute} = '{b.value}'[/white] "
        f"(Conf: {b.confidence:.2f}, Version: {b.version})"
    )

    # Version history branch
    hist_branch = root.add(f"[bold yellow]Version History ({len(prov.history)} revisions)[/bold yellow]")
    for h in prov.history:
        hist_branch.add(
            f"v{h['version']}: '{h['new_value']}' (Conf: {h['new_confidence']:.2f}) by fact {h['changed_by_fact_id']} "
            f"- [italic]{h.get('reason') or ''}[/italic]"
        )

    # Supporting facts branch
    sup_branch = root.add(f"[bold cyan]Supporting Facts ({len(prov.supporting_facts)})[/bold cyan]")
    for f in prov.supporting_facts:
        sup_branch.add(
            f"Fact [bold]{f.id}[/bold] ({f.source_reliability.upper()} reliability, {f.source}): \"{f.content}\""
        )

    # Contradicting facts branch
    if prov.contradicting_facts:
        con_branch = root.add(f"[bold red]Contradicting Facts ({len(prov.contradicting_facts)})[/bold red]")
        for f in prov.contradicting_facts:
            con_branch.add(
                f"Fact [bold]{f.id}[/bold] ({f.source_reliability.upper()} reliability, {f.source}): \"{f.content}\""
            )

    # Conflicts & resolutions branch
    if prov.conflicts:
        conf_branch = root.add(f"[bold magenta]Associated Conflicts ({len(prov.conflicts)})[/bold magenta]")
        for c in prov.conflicts:
            res_text = f" -> Winner: {c.resolution.winner} via {c.resolution.strategy_used}" if c.resolution else ""
            conf_branch.add(
                f"[{c.severity.upper()}] {c.conflict_type}: {c.description}{res_text}"
            )

    console.print(Panel(root, title="[bold]Complete Belief Provenance Chain[/bold]", box=ROUNDED))


def print_summary_dashboard(stats: dict[str, Any]) -> None:
    """Render a Rich summary dashboard."""
    grid = Table.grid(expand=True, padding=1)
    grid.add_column()
    grid.add_column()

    stats_table = Table(title="System Overview", box=ROUNDED)
    stats_table.add_column("Metric", style="bold cyan")
    stats_table.add_column("Value", style="bold white")

    stats_table.add_row("Total Facts Ingested", str(stats.get("total_facts", 0)))
    stats_table.add_row("Active Beliefs", str(stats.get("active_beliefs", 0)))
    stats_table.add_row("Total Conflicts Detected", str(stats.get("total_conflicts", 0)))
    stats_table.add_row("Active Resolution Strategy", f"[bold green]{stats.get('active_strategy')}[/bold green]")
    stats_table.add_row("Primary LLM Provider", str(stats.get("primary_llm")))
    stats_table.add_row("Secondary LLM Provider", str(stats.get("secondary_llm")))

    console.print(stats_table)
