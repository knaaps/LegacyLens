"""LegacyLens CLI - Index and query legacy code with multi-agent verification."""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from legacylens.retrieval.retriever import CodeRetriever
from legacylens.agents.orchestrator import generate_verified_explanation
from legacylens.analysis.call_graph import CallGraph
from legacylens.analysis.context_slicer import build_hybrid_context
from legacylens.analysis.codebalance import score_code

console = Console()

# Global call graph (built during indexing, used during explain)
_call_graph: CallGraph | None = None


def cmd_index(args: argparse.Namespace) -> int:
    """Index a repository and build call graph."""
    global _call_graph
    repo_path = Path(args.path).resolve()
    
    if not repo_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {repo_path}")
        return 1
    
    console.print(f"[bold]Indexing repository:[/bold] {repo_path}")
    
    retriever = CodeRetriever(db_path=args.db_path)
    
    with console.status("[bold green]Parsing and embedding code..."):
        stats = retriever.index_repository(repo_path)
    
    # Build call graph from indexed functions
    with console.status("[bold green]Building call graph..."):
        _call_graph = _build_call_graph_from_db(retriever)
    
    # Display results
    table = Table(title="Indexing Complete")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Files Processed", str(stats["files_processed"]))
    table.add_row("Functions Indexed", str(stats["functions_indexed"]))
    table.add_row("Graph Nodes", str(len(_call_graph)) if _call_graph else "0")
    table.add_row("Files Skipped", str(stats["files_skipped"]))
    table.add_row("Errors", str(len(stats["errors"])))
    
    console.print(table)
    
    if stats["errors"]:
        console.print("\n[yellow]Errors:[/yellow]")
        for error in stats["errors"][:5]:  # Show first 5
            console.print(f"  • {error}")
    
    return 0


def _build_call_graph_from_db(retriever: CodeRetriever) -> CallGraph:
    """Build call graph from all indexed functions."""
    graph = CallGraph()
    
    # Get all functions from the embedder
    embedder = retriever.embedder
    embedder._ensure_db_connected()
    
    # Query all documents
    results = embedder._collection.get(
        include=["documents", "metadatas"],
    )
    
    if not results["ids"]:
        return graph
    
    for i, doc_id in enumerate(results["ids"]):
        meta = results["metadatas"][i]
        code = results["documents"][i]
        
        # Parse calls from metadata
        calls_str = meta.get("calls", "")
        calls = [c.strip() for c in calls_str.split(",") if c.strip()]
        
        graph.add_function(
            name=meta.get("name", "unknown"),
            qualified_name=meta.get("qualified_name", doc_id),
            file_path=meta.get("file_path", ""),
            code=code,
            calls=calls,
        )
    
    return graph


def cmd_query(args: argparse.Namespace) -> int:
    """Query the indexed codebase."""
    query = args.query
    
    console.print(f"\n[bold]Query:[/bold] {query}\n")
    
    retriever = CodeRetriever(db_path=args.db_path)
    
    # Check if anything is indexed
    stats = retriever.get_stats()
    if stats["total_functions"] == 0:
        console.print("[red]Error:[/red] No code indexed. Run 'legacylens index <path>' first.")
        return 1
    
    results = retriever.search(query, top_k=args.top_k, language=args.language)
    
    if not results:
        console.print("[yellow]No matching code found.[/yellow]")
        return 0
    
    for i, result in enumerate(results, 1):
        meta = result["metadata"]
        
        # Header
        console.print(Panel(
            f"[bold cyan]{meta['qualified_name']}[/bold cyan]\n"
            f"File: {meta['file_path']}:{meta['start_line']}-{meta['end_line']}\n"
            f"Complexity: {meta['complexity']} | Lines: {meta['line_count']} | "
            f"Similarity: {1 - result['distance']:.2%}",
            title=f"Result {i}",
        ))
        
        # Code with syntax highlighting
        syntax = Syntax(
            result["code"],
            meta["language"],
            theme="monokai",
            line_numbers=True,
            start_line=int(meta["start_line"]),
        )
        console.print(syntax)
        console.print()
    
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Show database statistics."""
    retriever = CodeRetriever(db_path=args.db_path)
    stats = retriever.get_stats()
    
    table = Table(title="LegacyLens Database Stats")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Functions", str(stats["total_functions"]))
    table.add_row("Collection", stats["collection_name"])
    table.add_row("DB Path", stats["db_path"])
    
    console.print(table)
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Explain code using multi-agent verification."""
    global _call_graph
    query = args.query
    
    console.print(f"\n[bold]Explaining:[/bold] {query}\n")
    
    retriever = CodeRetriever(db_path=args.db_path)
    
    # Check if anything is indexed
    stats = retriever.get_stats()
    if stats["total_functions"] == 0:
        console.print("[red]Error:[/red] No code indexed. Run 'legacylens index <path>' first.")
        return 1
    
    # Build call graph if not available
    if _call_graph is None or len(_call_graph) == 0:
        with console.status("[bold green]Building call graph..."):
            _call_graph = _build_call_graph_from_db(retriever)
    
    # Get RAG results for fallback
    rag_results = retriever.search(query, top_k=3)
    
    if not rag_results:
        console.print("[yellow]No matching code found.[/yellow]")
        return 0
    
    # Build hybrid context (deterministic first, RAG fallback)
    context = build_hybrid_context(query, _call_graph, rag_results)
    code = context.get("code", rag_results[0]["code"])
    
    # Get metadata for display
    meta = rag_results[0]["metadata"]
    
    # Show the retrieved code
    console.print(Panel(
        f"[bold cyan]{meta['qualified_name']}[/bold cyan]\n"
        f"File: {meta['file_path']}:{meta['start_line']}-{meta['end_line']}\n"
        f"Context Source: {context.get('source', 'unknown')}",
        title="Target Code",
    ))
    
    syntax = Syntax(
        code,
        meta["language"],
        theme="monokai",
        line_numbers=True,
        start_line=int(meta["start_line"]),
    )
    console.print(syntax)
    console.print()
    
    # Show related functions if deterministic context found
    if context.get("callers"):
        console.print("[dim]Related: Callers found in graph[/dim]")
    if context.get("callees"):
        console.print("[dim]Related: Callees found in graph[/dim]")
    
    # Generate verified explanation using Writer→Critic loop
    console.print("\n[bold green]Running Writer→Critic verification loop...[/bold green]\n")
    
    result = generate_verified_explanation(
        code=code,
        context=context,
        max_iterations=2,
    )
    
    # Display verification status
    if result.verified:
        status_style = "green"
        status_icon = "✓"
    else:
        status_style = "yellow"
        status_icon = "⚠"
    
    console.print(Panel(
        f"[bold {status_style}]{status_icon} {result.status_string}[/bold {status_style}]\n"
        f"Iterations: {result.iterations}",
        title="Verification Status",
        border_style=status_style,
    ))
    
    # Show issues if any
    if result.critique and result.critique.issues:
        console.print(f"[yellow]Issues:[/yellow] {', '.join(result.critique.issues)}")
    
    # Display the explanation
    console.print(Panel(
        result.explanation,
        title="Explanation",
        border_style="green" if result.verified else "yellow",
    ))
    
    # --- Phase 3: CodeBalance ---
    console.print("\n[bold]CodeBalance Health Check:[/bold]\n")
    
    # Get function name from metadata for recursion detection
    func_name = meta.get("name", "")
    balance = score_code(code, function_name=func_name)
    
    # Color-code each score (0-3 green, 4-6 yellow, 7-10 red)
    def _color(score: int) -> str:
        if score <= 3:
            return f"[green]{score}/10[/green]"
        elif score <= 6:
            return f"[yellow]{score}/10[/yellow]"
        else:
            return f"[red]{score}/10[/red]"
    
    # Grade color
    grade_colors = {"A": "green", "B": "green", "C": "yellow", "D": "red", "F": "red"}
    grade_color = grade_colors.get(balance.grade, "white")
    
    # Build score table
    score_table = Table(title=f"Grade: [{grade_color}]{balance.grade}[/{grade_color}]")
    score_table.add_column("Axis", style="cyan")
    score_table.add_column("Score", justify="center")
    score_table.add_column("Details", style="dim")
    
    # Energy row
    energy_detail = ", ".join(balance.details.get("energy", {}).values()) or "No concerns"
    score_table.add_row("⚡ Energy", _color(balance.energy), energy_detail)
    
    # Debt row
    debt_detail = ", ".join(balance.details.get("debt", {}).values()) or "Clean code"
    score_table.add_row("🔧 Debt", _color(balance.debt), debt_detail)
    
    # Safety row
    safety_details = balance.details.get("safety", {})
    safety_issues = safety_details.get("issues", [])
    safety_detail = ", ".join(safety_issues) if safety_issues else "No risks detected"
    score_table.add_row("🛡️ Safety", _color(balance.safety), safety_detail)
    
    console.print(score_table)
    
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="legacylens",
        description="Understand legacy code through AI + static analysis verification",
    )
    parser.add_argument(
        "--db-path",
        default="./legacylens_db",
        help="Path to the vector database (default: ./legacylens_db)",
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Index command
    index_parser = subparsers.add_parser("index", help="Index a repository")
    index_parser.add_argument("path", help="Path to the repository")
    index_parser.set_defaults(func=cmd_index)
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Query the indexed codebase")
    query_parser.add_argument("query", help="Natural language query or code snippet")
    query_parser.add_argument(
        "-k", "--top-k",
        type=int,
        default=5,
        help="Number of results to return (default: 5)",
    )
    query_parser.add_argument(
        "-l", "--language",
        choices=["java", "python"],
        help="Filter by language",
    )
    query_parser.set_defaults(func=cmd_query)
    
    # Explain command
    explain_parser = subparsers.add_parser("explain", help="Explain code using AI")
    explain_parser.add_argument("query", help="What to explain (e.g., 'processFindForm')")
    explain_parser.set_defaults(func=cmd_explain)
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.set_defaults(func=cmd_stats)
    
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

