#!/usr/bin/env python3
"""
LegacyLens — Faculty Live Demo
================================
Walks through all Phase 1 capabilities on Spring PetClinic.

Usage:
    LLM_PROVIDER=groq python faculty_demo.py
"""

import contextlib
import io
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

# Add src to path if running from root
sys.path.insert(0, str(Path(__file__).parent / "src"))

from legacylens.parser import JavaParser, FunctionMetadata
from legacylens.embeddings import CodeEmbedder
from legacylens.analysis import CallGraph, slice_context, score_code, SlicedContext
from legacylens.agents import generate_verified_explanation

# ── CONFIGURATION ──────────────────────────────────────────

PETCLINIC_PATH = Path("data/spring-petclinic")
OWNER_CTRL_PATH = PETCLINIC_PATH / "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java"
DEFAULT_TARGET_FUNCTION = "processFindForm"

console = Console(width=70)


# ── UTILITIES ──────────────────────────────────────────────

def header(step: int, title: str) -> None:
    console.print(f"\n[bold white on blue]  STEP {step}  [/] [bold]{title}[/bold]\n")


def done(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}")


def warn(msg: str) -> None:
    console.print(f"  [yellow]⚠[/yellow] {msg}")


def fail(msg: str) -> None:
    console.print(f"  [red]✗[/red] {msg}")
    sys.exit(1)


@contextlib.contextmanager
def quiet():
    """Suppress stdout prints from library internals."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def pause() -> None:
    console.print("\n[dim]  ↵ Enter to continue...[/dim]", end="")
    input()
    print()


# ── STEP 1: AST Parsing ────────────────────────────────────

def step_1() -> Tuple[List[FunctionMetadata], JavaParser]:
    header(1, "AST Parsing  (Tree-Sitter)")

    if not OWNER_CTRL_PATH.exists():
        fail(f"Target file not found: {OWNER_CTRL_PATH}")

    parser = JavaParser()

    java_files = list(PETCLINIC_PATH.rglob("*.java"))
    console.print(f"  Scanning PetClinic → [cyan]{len(java_files)}[/] Java files found")

    functions = parser.parse_file(OWNER_CTRL_PATH)
    console.print(f"  Parsed OwnerController → [cyan]{len(functions)}[/] methods\n")

    t = Table(box=box.SIMPLE_HEAVY, padding=(0, 1))
    t.add_column("Method", style="white")
    t.add_column("Lines", justify="right", style="cyan")
    t.add_column("CC", justify="right", style="yellow")

    for fn in functions[:6]:
        t.add_row(fn.name, str(fn.line_count), str(fn.complexity))
    console.print(t)

    done("Extracts functions, complexity, and call edges from AST")
    return functions, parser


# ── STEP 2: Semantic Search ────────────────────────────────

def step_2(functions: List[FunctionMetadata]) -> CodeEmbedder:
    header(2, "Semantic Search  (CodeBERT + ChromaDB)")

    embedder = CodeEmbedder()

    # Clear stale data so results are clean
    with quiet():
        embedder.clear()

    console.print("  Loading CodeBERT & indexing functions...")
    with quiet():
        embedder.store_batch(functions)
    console.print(f"  Indexed [cyan]{len(functions)}[/] embeddings\n")

    query = "find owner by last name"
    console.print(f'  Query: [italic]"{query}"[/italic]\n')

    results = embedder.search(query, top_k=3)

    for i, r in enumerate(results, 1):
        name = r["metadata"].get("qualified_name", "?")
        dist = r["distance"]
        console.print(f"    {i}. [white]{name:<35}[/] dist=[cyan]{dist:.4f}[/]")

    done("Finds relevant code by meaning, not keywords")
    return embedder


# ── STEP 3: Hybrid Context ─────────────────────────────────

def step_3(parser: JavaParser) -> Optional[SlicedContext]:
    header(3, "Hybrid Context  (Call Graph + RAG)")

    console.print("  Building call graph...")

    # Parse all owner-package files (where processFindForm lives)
    # in a real app, this would be the whole codebase or a larger slice
    owner_dir = PETCLINIC_PATH / "src/main/java/org/springframework/samples/petclinic/owner"
    
    if not owner_dir.exists():
        fail(f"Owner directory not found: {owner_dir}")

    all_fns = []
    for jf in owner_dir.glob("*.java"):
        try:
            all_fns.extend(parser.parse_file(jf))
        except Exception:
            pass

    graph = CallGraph()
    for fn in all_fns:
        graph.add_function(
            name=fn.name,
            qualified_name=fn.qualified_name,
            file_path=fn.file_path,
            code=fn.code,
            calls=fn.calls,
        )

    console.print(f"  Graph nodes: [cyan]{graph.size}[/]")

    target = DEFAULT_TARGET_FUNCTION
    ctx = slice_context(target, graph)

    if ctx:
        console.print(f"  Target: [white]{ctx.target.qualified_name}[/]")
        console.print(f"  Callers: [cyan]{len(ctx.callers)}[/]  Callees: [cyan]{len(ctx.callees)}[/]")
        if ctx.callees:
            names = ", ".join(c.name for c in ctx.callees[:3])
            console.print(f"    └─ calls → [dim]{names}[/dim]")
        done("Deterministic 1-hop context assembled from call graph")
    else:
        # In this clean slate version, we want to know if context fails
        warn(f"Target '{target}' not found in graph.")
    
    return ctx


# ── STEP 4: Multi-Agent Verification ───────────────────────

def step_4(ctx: Optional[SlicedContext]) -> str:
    header(4, "Multi-Agent Verification  (Writer → Critic → Regen)")

    os.environ.setdefault("LLM_PROVIDER", "groq")
    provider = os.environ.get("LLM_PROVIDER", "local")
    console.print(f"  Provider: [cyan]{provider}[/]")
    console.print("  Running Writer → Critic → Regeneration...\n")

    if not ctx:
        fail("Cannot proceed to verification: Context slice is missing.")
        return "" # Static analysis satisfaction

    code = ctx.target.code
    context = ctx.to_context_dict()

    try:
        result = generate_verified_explanation(
            code=code, 
            context=context,
            max_iterations=2, 
            run_regeneration=True, 
            language="java",
        )
    except Exception as e:
        fail(f"Agent execution failed: {e}")
        return code

    # Show explanation (preview)
    preview = result.explanation[:300].strip()
    if len(result.explanation) > 300:
        preview += " ..."
    console.print(Panel(preview, border_style="green", padding=(0, 1)))

    # Metrics — clean single table
    console.print()
    verified_str = "[green]PASS[/]" if result.verified else "[red]FAIL[/]"
    console.print(f"  Verified:     {verified_str}")
    console.print(f"  Confidence:   [cyan]{result.confidence}%[/]")
    console.print(f"  Iterations:   {result.iterations}")

    if result.critique:
        fc = "[green]✓[/]" if result.critique.factual_passed else "[red]✗[/]"
        console.print(f"  Factual:      {fc}")
        console.print(f"  Completeness: [cyan]{result.critique.completeness_pct:.0f}%[/]")
        console.print(f"  Risks:        {len(result.critique.flagged_risks)}")

    if result.fidelity_score is not None:
        c = "green" if result.fidelity_score >= 0.7 else "yellow"
        console.print(f"  Fidelity:     [{c}]{result.fidelity_score:.0%}[/{c}]")

    if result.verified:
        done("Explanation verified by Compositional Critic + Regeneration")
    else:
        warn(f"Critic flagged issues (confidence {result.confidence}%) — demo continues")

    return code


# ── STEP 5: CodeBalance ────────────────────────────────────

def step_5(code: str, fn_name: str = DEFAULT_TARGET_FUNCTION) -> None:
    header(5, "CodeBalance  (Energy / Debt / Safety)")

    score = score_code(code, function_name=fn_name)

    axes = [
        ("⚡ Energy", score.energy),
        ("🔧 Debt",   score.debt),
        ("🛡️  Safety", score.safety),
    ]

    for label, val in axes:
        # Visual bar: 10 blocks total
        bar = "█" * val + "░" * (10 - val)
        c = "green" if val <= 3 else ("yellow" if val <= 6 else "red")
        console.print(f"  {label:12s} [{c}]{bar}[/{c}]  [{c}]{val}/10[/{c}]")

    console.print(f"\n  Grade: [bold]{score.grade}[/]  (total {score.total}/30)")

    # Show safety issues if any
    issues = score.details.get("safety", {}).get("issues", [])
    if issues:
        console.print()
        for iss in issues[:3]:
            warn(iss)

    done("3-axis health score beyond cyclomatic complexity")


# ── MAIN ───────────────────────────────────────────────────

def main() -> None:
    console.print(Panel(
        "[bold]LegacyLens[/bold] — Faculty Demo\n"
        "[dim]Target: Spring PetClinic  ·  "
        f"LLM: {os.environ.get('LLM_PROVIDER', 'local')}[/dim]",
        border_style="blue", padding=(0, 2),
    ))

    if not PETCLINIC_PATH.exists():
        console.print(f"[red]PetClinic not found at {PETCLINIC_PATH}[/]")
        console.print("[dim]Please ensure the submodule is initialized or the data directory is correct.[/dim]")
        sys.exit(1)

    try:
        # Step 1: Parsing
        functions, parser = step_1()
        pause()

        # Step 2: Search
        step_2(functions)
        pause()

        # Step 3: Context
        ctx = step_3(parser)
        pause()

        # Step 4: Verification (Requires Context)
        if ctx:
            code = step_4(ctx)
            pause()

            # Step 5: Scoring
            step_5(code)
            console.print("\n[bold green]✅ All 5 capabilities demonstrated.[/bold green]\n")
        else:
            fail("Demo halted: Could not build context for target function.")

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped by user.[/dim]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Fatal Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
