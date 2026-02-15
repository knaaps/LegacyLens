#!/usr/bin/env python3
"""
LegacyLens — Faculty Live Demo
================================
Walks through all Phase 1 capabilities on Spring PetClinic.

Usage:
    LLM_PROVIDER=groq python faculty_demo.py
"""

import contextlib, io, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console(width=70)

PETCLINIC = Path("data/spring-petclinic")
OWNER_CTRL = PETCLINIC / "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java"


def header(step: int, title: str):
    console.print(f"\n[bold white on blue]  STEP {step}  [/] [bold]{title}[/bold]\n")


def done(msg: str):
    console.print(f"  [green]✓[/green] {msg}")


def warn(msg: str):
    console.print(f"  [yellow]⚠[/yellow] {msg}")


def quiet():
    """Suppress stdout prints from library internals."""
    return contextlib.redirect_stdout(io.StringIO())


def pause():
    console.print("\n[dim]  ↵ Enter to continue...[/dim]", end="")
    input()
    print()


# ── STEP 1 ─────────────────────────────────────────────────

def step_1():
    header(1, "AST Parsing  (Tree-Sitter)")

    from legacylens.parser import JavaParser
    parser = JavaParser()

    java_files = list(PETCLINIC.rglob("*.java"))
    console.print(f"  Scanning PetClinic → [cyan]{len(java_files)}[/] Java files found")

    functions = parser.parse_file(OWNER_CTRL)
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


# ── STEP 2 ─────────────────────────────────────────────────

def step_2(functions):
    header(2, "Semantic Search  (CodeBERT + ChromaDB)")

    from legacylens.embeddings import CodeEmbedder
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


# ── STEP 3 ─────────────────────────────────────────────────

def step_3(parser):
    header(3, "Hybrid Context  (Call Graph + RAG)")

    from legacylens.analysis import CallGraph, slice_context

    console.print("  Building call graph...")

    # Parse all owner-package files (where processFindForm lives)
    owner_dir = PETCLINIC / "src/main/java/org/springframework/samples/petclinic/owner"
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

    target = "processFindForm"
    ctx = slice_context(target, graph)

    if ctx:
        console.print(f"  Target: [white]{ctx.target.qualified_name}[/]")
        console.print(f"  Callers: [cyan]{len(ctx.callers)}[/]  Callees: [cyan]{len(ctx.callees)}[/]")
        if ctx.callees:
            names = ", ".join(c.name for c in ctx.callees[:3])
            console.print(f"    └─ calls → [dim]{names}[/dim]")
        done("Deterministic 1-hop context assembled from call graph")
    else:
        warn("Target not in graph — RAG fallback would activate")

    return ctx


# ── STEP 4 ─────────────────────────────────────────────────

def step_4(ctx):
    header(4, "Multi-Agent Verification  (Writer → Critic → Regen)")

    from legacylens.agents import generate_verified_explanation

    os.environ.setdefault("LLM_PROVIDER", "groq")
    console.print(f"  Provider: [cyan]{os.environ.get('LLM_PROVIDER', 'local')}[/]")
    console.print("  Running Writer → Critic → Regeneration...\n")

    if ctx:
        code = ctx.target.code
        context = ctx.to_context_dict()
    else:
        code = '''\
@GetMapping("/owners")
public String processFindForm(@RequestParam(defaultValue = "1") int page,
        Owner owner, BindingResult result, Model model) {
    if (owner.getLastName() == null) {
        owner.setLastName("");
    }
    Page<Owner> ownersResults = findPaginatedForOwnersLastName(page, owner.getLastName());
    if (ownersResults.isEmpty()) {
        result.rejectValue("lastName", "notFound", "not found");
        return "owners/findOwners";
    }
    if (ownersResults.getTotalElements() == 1) {
        owner = ownersResults.iterator().next();
        return "redirect:/owners/" + owner.getId();
    }
    return addPaginationModel(page, model, ownersResults);
}'''
        context = {
            "static_facts": {
                "complexity": 4, "line_count": 18,
                "calls": ["findPaginatedForOwnersLastName", "rejectValue", "addPaginationModel"],
            }
        }

    result = generate_verified_explanation(
        code=code, context=context,
        max_iterations=2, run_regeneration=True, language="java",
    )

    # Show explanation (trimmed)
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


# ── STEP 5 ─────────────────────────────────────────────────

def step_5(code, fn_name="processFindForm"):
    header(5, "CodeBalance  (Energy / Debt / Safety)")

    from legacylens.analysis import score_code

    score = score_code(code, function_name=fn_name)

    axes = [
        ("⚡ Energy", score.energy),
        ("🔧 Debt",   score.debt),
        ("🛡️  Safety", score.safety),
    ]

    for label, val in axes:
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

def main():
    console.print(Panel(
        "[bold]LegacyLens[/bold] — Faculty Demo\n"
        "[dim]Target: Spring PetClinic  ·  "
        f"LLM: {os.environ.get('LLM_PROVIDER', 'local')}[/dim]",
        border_style="blue", padding=(0, 2),
    ))

    if not PETCLINIC.exists():
        console.print("[red]PetClinic not found at data/spring-petclinic[/]")
        sys.exit(1)

    try:
        functions, parser = step_1()
        pause()

        step_2(functions)
        pause()

        ctx = step_3(parser)
        pause()

        code = step_4(ctx)
        pause()

        step_5(code)

        console.print("\n[bold green]✅ All 5 capabilities demonstrated.[/bold green]\n")

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
