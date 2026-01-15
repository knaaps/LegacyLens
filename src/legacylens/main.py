"""LegacyLens CLI - Index and query legacy code."""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from legacylens.retrieval.retriever import CodeRetriever
from legacylens.generation.generator import generate_explanation

console = Console()


def cmd_index(args: argparse.Namespace) -> int:
    """Index a repository."""
    repo_path = Path(args.path).resolve()
    
    if not repo_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {repo_path}")
        return 1
    
    console.print(f"[bold]Indexing repository:[/bold] {repo_path}")
    
    retriever = CodeRetriever(db_path=args.db_path)
    
    with console.status("[bold green]Parsing and embedding code..."):
        stats = retriever.index_repository(repo_path)
    
    # Display results
    table = Table(title="Indexing Complete")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Files Processed", str(stats["files_processed"]))
    table.add_row("Functions Indexed", str(stats["functions_indexed"]))
    table.add_row("Files Skipped", str(stats["files_skipped"]))
    table.add_row("Errors", str(len(stats["errors"])))
    
    console.print(table)
    
    if stats["errors"]:
        console.print("\n[yellow]Errors:[/yellow]")
        for error in stats["errors"][:5]:  # Show first 5
            console.print(f"  • {error}")
    
    return 0


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
    """Explain code using AI."""
    query = args.query
    
    console.print(f"\n[bold]Explaining:[/bold] {query}\n")
    
    retriever = CodeRetriever(db_path=args.db_path)
    
    # Check if anything is indexed
    stats = retriever.get_stats()
    if stats["total_functions"] == 0:
        console.print("[red]Error:[/red] No code indexed. Run 'legacylens index <path>' first.")
        return 1
    
    # Retrieve relevant code
    results = retriever.search(query, top_k=1)
    
    if not results:
        console.print("[yellow]No matching code found.[/yellow]")
        return 0
    
    result = results[0]
    meta = result["metadata"]
    code = result["code"]
    
    # Show the retrieved code
    console.print(Panel(
        f"[bold cyan]{meta['qualified_name']}[/bold cyan]\n"
        f"File: {meta['file_path']}:{meta['start_line']}-{meta['end_line']}",
        title="Retrieved Code",
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
    
    # Generate explanation
    console.print("[bold green]Generating explanation...[/bold green]\n")
    
    explanation = generate_explanation(code, query, meta)
    
    console.print(Panel(explanation, title="Explanation", border_style="green"))
    
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
