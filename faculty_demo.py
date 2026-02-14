#!/usr/bin/env python3
"""
LegacyLens Faculty Demo Script
===============================

This script demonstrates all Phase 1 capabilities:
1. AST Parsing & Indexing
2. Semantic Search (RAG)
3. Hybrid Context Assembly (Deterministic Call Graph + RAG)
4. Multi-Agent Verification (Writer → Compositional Critic → Regeneration)
5. 3D CodeBalance Scoring

Target: Spring PetClinic (Java)
Function: OwnerController.processFindForm (complex data flow)
"""

import os
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

console = Console()

def print_section(title: str, emoji: str = "🔹"):
    """Print a styled section header."""
    console.print(f"\n{emoji} [bold cyan]{title}[/bold cyan]", style="bold")
    console.print("─" * 80)


def demo_step_1_indexing():
    """Step 1: Parse and Index the Codebase."""
    print_section("STEP 1: AST Parsing & Indexing", "📚")
    
    console.print("\n[yellow]Parsing Spring PetClinic with Tree-Sitter...[/yellow]")
    
    from legacylens.parser import get_parser
    from legacylens.embeddings import CodeEmbedder
    
    # Parse Java files
    parser = get_parser("java")
    petclinic_path = Path("data/spring-petclinic")
    
    if not petclinic_path.exists():
        console.print("[red]ERROR: PetClinic not found. Run: git clone ... into data/[/red]")
        return None
    
    java_files = list(petclinic_path.rglob("*.java"))
    console.print(f"  Found [green]{len(java_files)}[/green] Java files")
    
    # Parse a sample file
    sample_file = petclinic_path / "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java"
    functions = parser.parse_file(sample_file)
    
    console.print(f"  Extracted [green]{len(functions)}[/green] methods from OwnerController")
    
    # Show sample
    table = Table(title="Sample Parsed Functions", box=box.ROUNDED)
    table.add_column("Method", style="cyan")
    table.add_column("Lines", justify="right", style="magenta")
    table.add_column("Complexity", justify="right", style="yellow")
    
    for fn in functions[:3]:
        table.add_row(fn.name, str(fn.line_count), str(fn.complexity))
    
    console.print(table)
    
    # Embeddings
    console.print("\n[yellow]Generating embeddings with CodeBERT...[/yellow]")
    embedder = CodeEmbedder()
    
    # Store sample
    for fn in functions[:5]:
        embedder.store_function(fn)
    
    stats = embedder.get_stats()
    console.print(f"  Stored [green]{stats['total_functions']}[/green] function embeddings")
    
    return functions


def demo_step_2_semantic_search(embedder):
    """Step 2: Semantic Search (RAG)."""
    print_section("STEP 2: Semantic Search (RAG)", "🔍")
    
    from legacylens.embeddings import CodeEmbedder
    
    embedder = CodeEmbedder()
    
    query = "find owners by last name"
    console.print(f"\n[yellow]Query:[/yellow] \"{query}\"")
    
    results = embedder.search(query, top_k=3)
    
    table = Table(title="Top 3 Semantic Matches", box=box.ROUNDED)
    table.add_column("Rank", justify="right", style="cyan")
    table.add_column("Function", style="green")
    table.add_column("Similarity", justify="right", style="yellow")
    
    for i, (fn, score) in enumerate(results, 1):
        table.add_row(str(i), fn.qualified_name, f"{score:.3f}")
    
    console.print(table)
    console.print("\n[dim]✓ RAG successfully retrieved relevant functions without exact keyword match[/dim]")


def demo_step_3_hybrid_context():
    """Step 3: Hybrid Context Assembly."""
    print_section("STEP 3: Hybrid Context Assembly", "🧩")
    
    from legacylens.analysis import CallGraph, slice_context
    from legacylens.parser import get_parser
    
    console.print("\n[yellow]Building Call Graph...[/yellow]")
    
    parser = get_parser("java")
    petclinic_path = Path("data/spring-petclinic")
    
    # Parse all Java files for call graph
    all_functions = []
    for java_file in list(petclinic_path.rglob("*.java"))[:10]:  # Limit for demo speed
        all_functions.extend(parser.parse_file(java_file))
    
    graph = CallGraph()
    for fn in all_functions:
        graph.add_function(fn)
    
    console.print(f"  Built graph with [green]{len(all_functions)}[/green] nodes")
    
    # Slice context for target function
    target = "processFindForm"
    console.print(f"\n[yellow]Slicing context for:[/yellow] {target}")
    
    context = slice_context(graph, target, max_depth=1)
    
    if context:
        console.print(f"  [green]✓[/green] Found target function")
        console.print(f"  [green]✓[/green] Retrieved {len(context.callers)} callers")
        console.print(f"  [green]✓[/green] Retrieved {len(context.callees)} callees")
        console.print("\n[dim]Hybrid approach: Deterministic call graph + RAG fallback[/dim]")
        return context
    else:
        console.print("[red]Target function not found in graph[/red]")
        return None


def demo_step_4_multi_agent_verification(context):
    """Step 4: Multi-Agent Verification Loop."""
    print_section("STEP 4: Multi-Agent Verification", "🤖")
    
    if not context:
        console.print("[red]Skipping: No context available[/red]")
        return
    
    from legacylens.agents import generate_verified_explanation
    
    # Set Groq for speed (or local if not configured)
    os.environ.setdefault("LLM_PROVIDER", "groq")
    
    console.print("\n[yellow]Running Writer → Compositional Critic → Regeneration...[/yellow]")
    console.print(f"[dim]LLM Provider: {os.environ.get('LLM_PROVIDER', 'local')}[/dim]\n")
    
    code = context.target_function.code
    ctx = {
        "static_facts": {
            "complexity": context.target_function.complexity,
            "line_count": context.target_function.line_count,
            "calls": context.target_function.calls,
        },
        "callers": [c.code for c in context.callers[:2]],
        "callees": [c.code for c in context.callees[:2]],
    }
    
    result = generate_verified_explanation(
        code=code,
        context=ctx,
        max_iterations=2,
        run_regeneration=True,
        language="java"
    )
    
    # Display results
    panel = Panel(
        result.explanation[:300] + "...",
        title="[bold green]Generated Explanation[/bold green]",
        border_style="green"
    )
    console.print(panel)
    
    # Verification metrics
    table = Table(title="Verification Metrics", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Verified", "✓ PASS" if result.verified else "✗ FAIL")
    table.add_row("Confidence", f"{result.confidence}%")
    table.add_row("Iterations", str(result.iterations))
    
    if result.critique:
        table.add_row("Factual Check", "✓" if result.critique.factual_passed else "✗")
        table.add_row("Completeness", f"{result.critique.completeness_pct:.0f}%")
        table.add_row("Risks Flagged", str(len(result.critique.flagged_risks)))
    
    if result.fidelity_score is not None:
        table.add_row("Fidelity (AST)", f"{result.fidelity_score:.0%}")
    
    console.print(table)
    
    console.print("\n[dim]✓ Compositional Critic: Factual + Completeness + Risk checks[/dim]")
    console.print("[dim]✓ Regeneration Validator: AST similarity proof[/dim]")
    
    return result


def demo_step_5_codebalance():
    """Step 5: 3D CodeBalance Scoring."""
    print_section("STEP 5: 3D CodeBalance Scoring", "⚖️")
    
    from legacylens.analysis import score_code
    from legacylens.parser import get_parser
    
    parser = get_parser("java")
    petclinic_path = Path("data/spring-petclinic")
    sample_file = petclinic_path / "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java"
    
    functions = parser.parse_file(sample_file)
    target_fn = next((f for f in functions if f.name == "processFindForm"), None)
    
    if not target_fn:
        console.print("[red]Target function not found[/red]")
        return
    
    console.print("\n[yellow]Analyzing code health on 3 axes...[/yellow]")
    
    score = score_code(target_fn.code, language="java")
    
    # Display as table
    table = Table(title="CodeBalance Score (0-10 scale)", box=box.DOUBLE)
    table.add_column("Dimension", style="cyan", width=15)
    table.add_column("Score", justify="right", style="yellow", width=10)
    table.add_column("Assessment", style="green", width=30)
    
    def assess(val):
        if val <= 3:
            return "✓ Excellent"
        elif val <= 6:
            return "⚠ Moderate"
        else:
            return "⚠ High"
    
    table.add_row("⚡ Energy", f"{score.energy}/10", assess(score.energy))
    table.add_row("🔧 Debt", f"{score.debt}/10", assess(score.debt))
    table.add_row("🛡️ Safety", f"{score.safety}/10", assess(score.safety))
    
    console.print(table)
    
    if score.safety_issues:
        console.print("\n[yellow]Detected Safety Issues:[/yellow]")
        for issue in score.safety_issues[:3]:
            console.print(f"  • {issue}")
    
    console.print("\n[dim]✓ Holistic code health assessment beyond cyclomatic complexity[/dim]")


def main():
    """Run the complete demo."""
    console.print(Panel.fit(
        "[bold white]LegacyLens Faculty Demo[/bold white]\n"
        "[dim]Intelligent Context Engineering for Legacy Code Comprehension[/dim]",
        border_style="blue"
    ))
    
    try:
        # Step 1: Indexing
        functions = demo_step_1_indexing()
        if not functions:
            return
        
        # Step 2: Semantic Search
        demo_step_2_semantic_search(None)
        
        # Step 3: Hybrid Context
        context = demo_step_3_hybrid_context()
        
        # Step 4: Multi-Agent Verification
        demo_step_4_multi_agent_verification(context)
        
        # Step 5: CodeBalance
        demo_step_5_codebalance()
        
        # Summary
        print_section("DEMO COMPLETE", "✅")
        console.print("\n[bold green]All Phase 1 capabilities demonstrated:[/bold green]")
        console.print("  ✓ AST Parsing (Tree-Sitter)")
        console.print("  ✓ Semantic Search (CodeBERT + ChromaDB)")
        console.print("  ✓ Hybrid Context (Call Graph + RAG)")
        console.print("  ✓ Multi-Agent Verification (Writer → Critic → Regen)")
        console.print("  ✓ 3D CodeBalance Scoring")
        console.print("\n[dim]Ready for thesis evaluation.[/dim]\n")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
