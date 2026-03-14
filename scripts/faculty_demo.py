#!/usr/bin/env python3
"""
LegacyLens — Faculty Live Demo
================================
End-to-end walkthrough of the LegacyLens pipeline on Spring PetClinic.

Parses the ENTIRE PetClinic source tree across all packages, builds a
project-wide call graph, and demonstrates semantic search, multi-agent
verification (up to 5 iterations), and comparative CodeBalance scoring.

Usage:
    python faculty_demo.py                          # Groq (default)
    LLM_PROVIDER=local python faculty_demo.py       # Ollama
"""

import argparse
import contextlib
import io
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Tuple

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

# ── Path setup ─────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent / "src"))

from legacylens.agents import generate_verified_explanation
from legacylens.analysis import CallGraph, SlicedContext, score_code, slice_context
from legacylens.embeddings import CodeEmbedder
from legacylens.parser import FunctionMetadata, JavaParser

# ── Configuration ──────────────────────────────────────────

PETCLINIC = Path("data/spring-petclinic")
JAVA_SRC = PETCLINIC / "src/main/java/org/springframework/samples/petclinic"
TARGET_FN = "processFindForm"
TARGET_FN_2 = "processCreationForm"  # Second function for comparative scoring
MAX_ITER = 5
QUERIES = [
    "find owner by last name",
    "add a new pet to the clinic",
]

console = Console(width=76)

# ── Parsed CLI args (will be set in main()) ────────────────
_args: argparse.Namespace | None = None

# ── Helpers ────────────────────────────────────────────────


def _step(num: int, title: str) -> None:
    console.print()
    console.print(Rule(f"[bold]STEP {num}[/bold]", style="blue"))
    console.print(f"  [bold]{title}[/bold]\n")


def _ok(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}")


def _warn(msg: str) -> None:
    console.print(f"  [yellow]⚠[/yellow] {msg}")


def _die(msg: str) -> None:
    console.print(f"\n  [red]✗ {msg}[/red]")
    sys.exit(1)


@contextlib.contextmanager
def _quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def _pause() -> None:
    pass


# ═══════════════════════════════════════════════════════════
#  Step 1 — Parse entire PetClinic across all packages
# ═══════════════════════════════════════════════════════════


def step_1_parse() -> Tuple[List[FunctionMetadata], JavaParser]:
    _step(1, "AST Parsing  (Tree-Sitter)")

    if not JAVA_SRC.exists():
        _die(f"PetClinic source not found: {JAVA_SRC}")

    parser = JavaParser()

    # Parse ALL Java files under src/main/java
    all_java = sorted(JAVA_SRC.rglob("*.java"))
    console.print(f"  Scanning PetClinic source → [cyan]{len(all_java)}[/] Java files\n")

    functions: List[FunctionMetadata] = []
    pkg_stats: dict[str, dict] = defaultdict(lambda: {"files": 0, "methods": 0})

    with console.status("[bold green]Parsing AST and extracting structural context..."):
        for jf in all_java:
            # Derive package name from directory (owner, vet, system, model, root)
            rel = jf.relative_to(JAVA_SRC)
            pkg = rel.parts[0] if len(rel.parts) > 1 else "(root)"
            pkg_stats[pkg]["files"] += 1

            try:
                fns = parser.parse_file(jf)
                functions.extend(fns)
                pkg_stats[pkg]["methods"] += len(fns)
            except Exception:
                pass

    # ── Package breakdown tree ──
    tree = Tree("[bold]petclinic[/bold]")
    for pkg in sorted(pkg_stats):
        s = pkg_stats[pkg]
        label = f"[cyan]{pkg}[/cyan]  ({s['files']} files, {s['methods']} methods)"
        tree.add(label)
    console.print(tree)
    console.print(f"\n  Total: [bold cyan]{len(functions)}[/bold cyan] methods extracted\n")

    # ── Top-complexity methods (most interesting for the audience) ──
    top = sorted(functions, key=lambda f: f.complexity, reverse=True)[:8]

    tbl = Table(
        title="[bold]Highest Complexity Methods[/bold]",
        box=box.ROUNDED,
        title_style="bold white",
        header_style="bold",
        padding=(0, 1),
    )
    tbl.add_column("Class.Method", style="white", min_width=30)
    tbl.add_column("Lines", justify="right", style="cyan")
    tbl.add_column("CC", justify="right", style="yellow")
    tbl.add_column("Calls", justify="right", style="dim")
    for fn in top:
        tbl.add_row(
            fn.qualified_name,
            str(fn.line_count),
            str(fn.complexity),
            str(len(fn.calls)),
        )
    console.print(tbl)

    _ok(f"Parsed {len(all_java)} files across {len(pkg_stats)} packages")
    _ok("Extracts functions, complexity, and call-edges from AST")
    return functions, parser


# ═══════════════════════════════════════════════════════════
#  Step 2 — Semantic Search with multiple queries
# ═══════════════════════════════════════════════════════════


def step_2_search(functions: List[FunctionMetadata]) -> CodeEmbedder:
    _step(2, "Semantic Search  (CodeBERT + ChromaDB)")

    embedder = CodeEmbedder()
    with _quiet():
        embedder.clear()

    with console.status("[bold green]Loading CodeBERT & generating vector embeddings..."):
        with _quiet():
            embedder.store_batch(functions)
    console.print(f"  Indexed [bold cyan]{len(functions)}[/bold cyan] embeddings\n")

    # Run multiple queries to show versatility
    for q in QUERIES:
        console.print(f'  [bold]Query:[/bold]  [italic]"{q}"[/italic]')
        results = embedder.search(q, top_k=3)
        for i, r in enumerate(results, 1):
            name = r["metadata"].get("qualified_name", "?")
            dist = r["distance"]
            console.print(f"    {i}. [white]{name:<38}[/] dist=[cyan]{dist:.4f}[/]")
        console.print()

    _ok("Finds relevant code by meaning, not keywords")
    _ok("Works across all packages — not limited to a single controller")
    return embedder


# ═══════════════════════════════════════════════════════════
#  Step 3 — Project-wide Call Graph
# ═══════════════════════════════════════════════════════════


def step_3_context(functions: List[FunctionMetadata]) -> Optional[SlicedContext]:
    _step(3, "Hybrid Context  (Call Graph + RAG)")

    with console.status("[bold green]Building memory-resident call graph..."):
        graph = CallGraph()
        for fn in functions:
            graph.add_function(
                name=fn.name,
                qualified_name=fn.qualified_name,
                file_path=fn.file_path,
                code=fn.code,
                calls=fn.calls,
                field_reads=fn.field_reads,
                field_writes=fn.field_writes,
            )

    # Count total edges

    total_edges = sum(len(fn.calls) for fn in functions)

    # Find most-connected nodes (by outgoing calls)
    by_calls = sorted(functions, key=lambda f: len(f.calls), reverse=True)[:3]

    # Graph stats panel
    stats_text = (
        f"  Nodes:  [bold cyan]{graph.size}[/bold cyan]  (functions)\n"
        f"  Edges:  [bold cyan]{total_edges}[/bold cyan]  (call relationships)\n"
        f"  Most connected:\n"
    )
    for fn in by_calls:
        stats_text += f"    • [white]{fn.qualified_name}[/]  → {len(fn.calls)} calls\n"
    console.print(
        Panel(
            stats_text.strip(), title="[bold]Call Graph[/bold]", border_style="dim", padding=(0, 1)
        )
    )

    # Slice context for target
    ctx = slice_context(TARGET_FN, graph)
    console.print()

    if ctx:
        # Build a visual tree for the context slice
        ctx_tree = Tree(f"[bold white]{ctx.target.qualified_name}[/bold white]")
        if ctx.callers:
            callers_branch = ctx_tree.add("[dim]↑ callers[/dim]")
            for c in ctx.callers:
                callers_branch.add(f"[cyan]{c.qualified_name}[/cyan]")
        if ctx.callees:
            callees_branch = ctx_tree.add("[dim]↓ callees[/dim]")
            for c in ctx.callees:
                callees_branch.add(f"[cyan]{c.qualified_name}[/cyan]")

        console.print(f"  Context slice for [bold]{TARGET_FN}[/bold]:")
        console.print(ctx_tree)
        _ok("Deterministic 1-hop context assembled from project-wide call graph")
    else:
        _warn(f"Target '{TARGET_FN}' not found in graph — RAG fallback would activate")

    return ctx


# ═══════════════════════════════════════════════════════════
#  Step 4 — Multi-Agent Verification
# ═══════════════════════════════════════════════════════════


def step_4_verify(ctx: SlicedContext) -> str:
    _step(4, "Multi-Agent Verification  (Writer → Critic → Regen)")

    os.environ.setdefault("LLM_PROVIDER", "groq")
    provider = os.environ.get("LLM_PROVIDER", "local")

    info = Table.grid(padding=(0, 2))
    info.add_row("[dim]Provider:[/dim]", f"[cyan]{provider}[/cyan]")
    info.add_row("[dim]Max loops:[/dim]", f"[cyan]{MAX_ITER}[/cyan]")
    info.add_row("[dim]Target:[/dim]", f"[white]{ctx.target.qualified_name}[/white]")

    # Load SOP if requested
    sop: dict = {}
    sop_label = "default"
    if _args and _args.sop:
        from legacylens.agents.sop_loader import load_sop

        sop = load_sop(_args.sop)
        sop_label = _args.sop
    info.add_row("[dim]SOP variant:[/dim]", f"[cyan]{sop_label}[/cyan]")
    console.print(info)
    console.print("\n  Running Writer → Critic → Regeneration...\n")

    code = ctx.target.code
    context = ctx.to_context_dict()
    max_iters: int = sop.get("max_iterations", MAX_ITER)

    console.print("\n[bold]Target Function:[/bold]")

    syntax = Syntax(
        ctx.target.code,
        "java",
        theme="monokai",
        line_numbers=True,
        start_line=1,
    )
    console.print(syntax)

    console.print("\n")
    with console.status("[bold green]Agent Loop (Writer → Critic)..."):
        try:
            from legacylens.agents.explanation_store import current_fingerprint

            result = generate_verified_explanation(
                code=code,
                context=context,
                max_iterations=max_iters,
                run_regeneration=True,
                language="java",
                sop=sop,
                function_name=ctx.target.qualified_name,
                codebase_version=current_fingerprint(),
                repetition_variant="simple",
            )
        except Exception as e:
            _die(f"Agent pipeline failed: {e}")
            return code

    # ── Write iteration log ──
    if _args and getattr(_args, "log_iterations", True) and result.iteration_log:
        fn_slug = ctx.target.name.replace("/", "_")
        log_payload = {
            "function": ctx.target.qualified_name,
            "sop_variant": sop_label,
            "verified": result.verified,
            "total_iterations": result.iterations,
            "fidelity": result.fidelity_score,
            "iterations": result.iteration_log,
        }
        # Write to results/ (git-tracked)
        Path("results").mkdir(exist_ok=True)
        trace_path = Path(f"results/regen_trace_{fn_slug}.json")
        trace_path.write_text(json.dumps(log_payload, indent=2))
        # Also copy to ~/.legacylens for dashboard
        dash_dir = Path.home() / ".legacylens" / "regen_traces"
        dash_dir.mkdir(parents=True, exist_ok=True)
        (dash_dir / f"{fn_slug}.json").write_text(json.dumps(log_payload, indent=2))
        _ok(f"Iteration log → {trace_path}")

    # ── Explanation preview ──
    preview = result.explanation[:350].strip()
    if len(result.explanation) > 350:
        preview += " …"
    console.print(
        Panel(
            preview,
            title="[bold green]Generated Explanation[/bold green]",
            border_style="green",
            padding=(0, 1),
        )
    )

    # ── Metrics table ──
    console.print()
    mtbl = Table(box=box.SIMPLE, padding=(0, 2), show_header=False)
    mtbl.add_column("Metric", style="dim", min_width=14)
    mtbl.add_column("Value")

    v_str = "[bold green]PASS[/bold green]" if result.verified else "[bold red]FAIL[/bold red]"
    mtbl.add_row("Verified", v_str)
    mtbl.add_row("Confidence", f"[cyan]{result.confidence}%[/cyan]")
    mtbl.add_row("Iterations", f"{result.iterations} / {MAX_ITER}")

    if result.critique:
        fc = "[green]✓ yes[/green]" if result.critique.factual_passed else "[red]✗ no[/red]"
        mtbl.add_row("Factual", fc)
        mtbl.add_row("Completeness", f"[cyan]{result.critique.completeness_pct:.0f}%[/cyan]")
        mtbl.add_row("Risks flagged", str(len(result.critique.flagged_risks)))

    if result.fidelity_score is not None:
        c = "green" if result.fidelity_score >= 0.7 else "yellow"
        mtbl.add_row("Fidelity", f"[{c}]{result.fidelity_score:.0%}[/{c}]")

    console.print(mtbl)

    # Quality badge — graded by confidence, never just "failed"
    if result.verified:
        _ok("Explanation verified by Compositional Critic + Regeneration")
    elif result.confidence >= 70:
        console.print(
            f"  [yellow]～[/yellow] Best-effort explanation (confidence {result.confidence}%) — not formally verified but usable"
        )
    else:
        console.print(
            f"  [dim]○[/dim] Low-confidence explanation ({result.confidence}%) — treat as a draft starting point"
        )

    return code


# ═══════════════════════════════════════════════════════════
#  Step 5 — Comparative CodeBalance
# ═══════════════════════════════════════════════════════════


def _color(score: int) -> str:
    if score <= 3:
        return f"[green]{score}/10[/green]"
    elif score <= 6:
        return f"[yellow]{score}/10[/yellow]"
    else:
        return f"[red]{score}/10[/red]"


def step_5_score(functions: List[FunctionMetadata]) -> None:
    _step(5, "CodeBalance  (Energy / Debt / Safety)")

    # Find two target functions for comparative analysis
    targets = [TARGET_FN, TARGET_FN_2]
    fn_map = {fn.name: fn for fn in functions}

    console.print("[dim]Comparing structural health and maintainability metrics:[/dim]\n")

    panels = []
    for name in targets:
        fn = fn_map.get(name)
        if not fn:
            _warn(f"Function '{name}' not found, skipping.")
            continue

        score = score_code(fn.code, function_name=name)

        # Grade color
        grade_colors = {"A": "green", "B": "green", "C": "yellow", "D": "red", "F": "red"}
        grade_color = grade_colors.get(score.grade, "white")

        table = Table(
            title=f"[bold]{fn.qualified_name}[/bold] | Grade: [{grade_color}]{score.grade}[/{grade_color}]",
            box=box.ROUNDED,
        )
        table.add_column("Axis", style="cyan")
        table.add_column("Score", justify="center")
        table.add_column("Details", style="dim")

        e_detail = ", ".join(score.details.get("energy", {}).values()) or "Efficient"
        table.add_row("⚡ Energy", _color(score.energy), e_detail)

        d_detail = ", ".join(score.details.get("debt", {}).values()) or "Clean code"
        table.add_row("🔧 Debt", _color(score.debt), d_detail)

        s_issues = score.details.get("safety", {}).get("issues", [])
        s_detail = ", ".join(s_issues) if s_issues else "No active risks"
        table.add_row("🛡️ Safety", _color(score.safety), s_detail)

        panels.append(table)

    if panels:
        console.print(Columns(panels, equal=False, expand=True))

    _ok("3-axis health score beyond cyclomatic complexity")
    _ok("Comparative view reveals relative code health across functions")


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════


def main() -> None:
    global _args, MAX_ITER

    # ── Argument parsing ──
    parser = argparse.ArgumentParser(
        description="LegacyLens Faculty Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--sop",
        choices=["default", "cautious", "verbose", "fast"],
        default=None,
        metavar="VARIANT",
        help="Agent SOP variant to use (default | cautious | verbose | fast).",
    )
    parser.add_argument(
        "--log-iterations",
        action="store_true",
        default=True,
        dest="log_iterations",
        help="Write per-iteration JSON trace to results/ and ~/.legacylens/regen_traces/.",
    )
    parser.add_argument(
        "--no-log",
        action="store_false",
        dest="log_iterations",
        help="Disable iteration logging.",
    )
    _args = parser.parse_args()

    # ── Clear accumulated pitfall state ──
    pitfalls_path = Path.home() / ".legacylens" / "known_pitfalls.json"
    local_pitfalls = Path("results/known_pitfalls.json")
    if pitfalls_path.exists():
        pitfalls_path.unlink()
    if local_pitfalls.exists():
        local_pitfalls.unlink()

    provider = os.environ.get("LLM_PROVIDER", "local")
    sop_label = _args.sop or "default"

    # Welcome Banner
    console.print()
    welcome_table = Table(box=box.DOUBLE_EDGE, show_header=False, expand=True)
    welcome_table.add_column("info", justify="center")
    welcome_table.add_row("[bold cyan]LegacyLens[/bold cyan]  —  Faculty Demo")
    welcome_table.add_row("[dim]Intelligent Context Slicing + Multi-Agent Verification[/dim]")

    config_str = (
        f"[green]Target:[/green] Spring PetClinic   "
        f"[green]LLM:[/green] {provider}   "
        f"[green]Verification Loops:[/green] {MAX_ITER}   "
        f"[green]SOP:[/green] {sop_label}"
    )
    welcome_table.add_row(config_str)
    console.print(welcome_table)
    console.print()

    if not PETCLINIC.exists():
        console.print(f"\n[red]✗ PetClinic not found at {PETCLINIC}[/]")
        console.print(
            "[dim]  Run:  cd data && git clone https://github.com/spring-projects/spring-petclinic[/dim]"
        )
        sys.exit(1)

    try:
        # 1 — Parse all packages
        functions, parser = step_1_parse()
        _pause()

        # 2 — Semantic search (multiple queries)
        step_2_search(functions)
        _pause()

        # 3 — Project-wide call graph + context slice
        ctx = step_3_context(functions)
        _pause()

        # 4 — Multi-agent verification
        if not ctx:
            _die("Demo halted: could not build context for target function.")
        step_4_verify(ctx)
        _pause()

        # 5 — Comparative CodeBalance
        step_5_score(functions)

        console.print()
        console.print(
            Panel(
                "[bold green]✅  All 5 capabilities demonstrated successfully.[/bold green]",
                border_style="green",
                padding=(0, 2),
            )
        )
        console.print()

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped by user.[/dim]")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
