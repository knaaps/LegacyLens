"""LegacyLens CLI - Index and query legacy code with multi-agent verification."""

import argparse
import json
import sys
import webbrowser
import threading
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
    
    with console.status("[bold green]Exporting data for dashboard..."):
        _export_function_data(retriever)
        # Save repo root so the dashboard can resolve relative paths
        data_dir = Path.home() / '.legacylens'
        data_dir.mkdir(exist_ok=True)
        (data_dir / 'repo_root.txt').write_text(str(repo_path))
    
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
        
        # Parse field access from metadata (comma-separated strings)
        fr_str = meta.get("field_reads", "")
        fw_str = meta.get("field_writes", "")
        f_reads = [f.strip() for f in fr_str.split(",") if f.strip()] if fr_str else []
        f_writes = [f.strip() for f in fw_str.split(",") if f.strip()] if fw_str else []
        
        graph.add_function(
            name=meta.get("name", "unknown"),
            qualified_name=meta.get("qualified_name", doc_id),
            file_path=meta.get("file_path", ""),
            code=code,
            calls=calls,
            field_reads=f_reads,
            field_writes=f_writes,
        )
    return graph


def _export_function_data(retriever: CodeRetriever) -> None:
    """Export function data to JSON for the web dashboard."""
    import json
    from legacylens.analysis.codebalance import score_code
    
    embedder = retriever.embedder
    embedder._ensure_db_connected()
    
    results = embedder._collection.get(include=["documents", "metadatas"])
    
    functions = []
    if results["ids"]:
        for i, doc_id in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            code = results["documents"][i]
            
            func_name = meta.get("name", "unknown")
            scores = score_code(code, function_name=func_name)
            
            functions.append({
                'name': meta.get("qualified_name", func_name),
                'file': meta.get("file_path", ""),
                'line_start': meta.get("start_line", 0),
                'line_end': meta.get("end_line", 0),
                'energy': scores.energy,
                'debt': scores.debt,
                'safety': scores.safety,
                'code': code
            })
            
    data_dir = Path.home() / '.legacylens'
    data_dir.mkdir(exist_ok=True)
    with open(data_dir / 'function_data.json', 'w') as f:
        json.dump(functions, f, indent=2)


def cmd_query(args: argparse.Namespace) -> int:
    """Query the indexed codebase."""
    query = args.query
    fmt = getattr(args, 'format', None)
    web = getattr(args, 'web', False)

    # --web: open browser search page
    if web:
        import urllib.parse
        url = f'http://127.0.0.1:5000/search?q={urllib.parse.quote(query)}'
        console.print(f"[bold green]Opening browser:[/bold green] {url}")
        webbrowser.open(url)
        return 0
    
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

    # --format json
    if fmt == 'json':
        out = []
        for result in results:
            meta = result["metadata"]
            out.append({
                'name': meta.get('qualified_name', ''),
                'file': meta.get('file_path', ''),
                'start_line': meta.get('start_line', 0),
                'end_line': meta.get('end_line', 0),
                'similarity': round(1 - result['distance'], 4),
                'code': result['code'],
            })
        print(json.dumps(out, indent=2))
        return 0

    # --format markdown
    if fmt == 'markdown':
        for i, result in enumerate(results, 1):
            meta = result["metadata"]
            print(f"## Result {i}: `{meta['qualified_name']}`")
            print(f"**File:** `{meta['file_path']}:{meta['start_line']}-{meta['end_line']}`")
            print(f"**Similarity:** {1 - result['distance']:.2%}\n")
            print(f"```{meta['language']}")
            print(result['code'])
            print("```\n")
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


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Launch the LegacyLens web dashboard."""
    import webbrowser
    import threading
    from legacylens.web.app import create_app
    
    port = args.port
    app = create_app()
    
    def open_browser():
        webbrowser.open(f'http://127.0.0.1:{port}')
    
    console.print(f"[bold green]Starting Dashboard on port {port}...[/bold green]")
    threading.Timer(1.5, open_browser).start()
    
    # Run the Flask app
    app.run(debug=False, port=port, use_reloader=False)
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Explain code using multi-agent verification."""
    global _call_graph
    query = args.query
    fmt = getattr(args, 'format', None)
    web = getattr(args, 'web', False)
    
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
    
    # Add a header for the function name
    func_name = meta.get("name", query)
    console.rule(f"[bold blue]Function: {func_name}")

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
        max_iterations=5,
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
        f"Verdict: {result.verdict} | Iterations: {result.iterations}",
        title="Verification Status",
        border_style=status_style,
    ))
    
    # Show critic's JSON verdict summary
    if result.critique_json:
        cj = result.critique_json
        console.print(
            f"  Factual: {'✓' if cj['factual_pass'] else '✗'} | "
            f"Complete: {cj['completeness_pct']:.0f}% | "
            f"Risks: {len(cj['risks_mentioned'])}"
        )
    
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
    
    # --web: open browser to the function's explain page
    if web:
        import urllib.parse
        url = f'http://127.0.0.1:5000/search?q={urllib.parse.quote(func_name)}'
        console.print(f"[bold green]Opening browser:[/bold green] {url}")
        webbrowser.open(url)
        return 0

    # --format json
    if fmt == 'json':
        out = {
            'function': meta.get('qualified_name', func_name),
            'file': meta.get('file_path', ''),
            'start_line': meta.get('start_line', 0),
            'end_line': meta.get('end_line', 0),
            'verified': result.verified,
            'verdict': result.verdict,
            'iterations': result.iterations,
            'explanation': result.explanation,
            'codebalance': {'energy': balance.energy, 'debt': balance.debt, 'safety': balance.safety, 'grade': balance.grade},
        }
        print(json.dumps(out, indent=2))
        return 0

    # --format markdown
    if fmt == 'markdown':
        print(f"# Explanation: `{meta.get('qualified_name', func_name)}`")
        print(f"**File:** `{meta.get('file_path', '')}:{meta.get('start_line', '')}–{meta.get('end_line', '')}`")
        print(f"**Verified:** {'✓' if result.verified else '⚠'} | **Verdict:** {result.verdict} | **Iterations:** {result.iterations}\n")
        print(result.explanation)
        print(f"\n## CodeBalance")
        print(f"| Axis | Score |\n|------|-------|")
        print(f"| ⚡ Energy | {balance.energy}/10 |")
        print(f"| 🔧 Debt | {balance.debt}/10 |")
        print(f"| 🛡 Safety | {balance.safety}/10 |")
        print(f"| **Grade** | **{balance.grade}** |")
        return 0

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
    query_parser.add_argument(
        "--web",
        action="store_true",
        help="Open results in the web dashboard",
    )
    query_parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default=None,
        help="Output format (json or markdown)",
    )
    query_parser.set_defaults(func=cmd_query)
    
    # Explain command
    explain_parser = subparsers.add_parser("explain", help="Explain code using AI")
    explain_parser.add_argument("query", help="What to explain (e.g., 'processFindForm')")
    explain_parser.add_argument(
        "--web",
        action="store_true",
        help="Open explanation in the web dashboard",
    )
    explain_parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default=None,
        help="Output format (json or markdown)",
    )
    explain_parser.set_defaults(func=cmd_explain)
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.set_defaults(func=cmd_stats)
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser("dashboard", help="Launch the web dashboard")
    dashboard_parser.add_argument("--port", type=int, default=5000, help="Port to run the server on")
    dashboard_parser.set_defaults(func=cmd_dashboard)
    
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

