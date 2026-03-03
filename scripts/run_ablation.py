"""Ablation Study Runner — Compare LegacyLens configurations on PetClinic functions.

Runs the full pipeline (Writer → Critic → Regeneration) on a corpus of
PetClinic functions under multiple configurations to measure uplift from:
  - Prompt repetition (Leviathan et al. 2025)
  - Structured feedback + meta-prompt accumulation (Kawabe-inspired)

Usage:
    # Run all ablation arms (requires LLM_PROVIDER=groq or running Ollama)
    LLM_PROVIDER=groq python3 scripts/run_ablation.py

    # Run specific arms only
    LLM_PROVIDER=groq python3 scripts/run_ablation.py --arms baseline,repetition

Output:
    results/ablation_results.csv   — raw per-function scores
    results/ablation_summary.md    — markdown table for thesis
"""

import sys
import os
import csv
import argparse
from pathlib import Path
from datetime import datetime

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from legacylens.agents.orchestrator import generate_verified_explanation

# Import BLEU/ROUGE scorer (same scripts/ directory, no extra deps)
sys.path.insert(0, str(Path(__file__).parent))
from metrics_scorer import score_explanation

# ---------------------------------------------------------------------------
# Test corpus — PetClinic functions (same 5 from test_e2e_batch + extras)
# ---------------------------------------------------------------------------

FUNCTIONS = [
    {
        "name": "OwnerController.initCreationForm",
        "category": "Simple View",
        "reference": "initCreationForm creates a new Owner object and adds it to the model, then returns the create or update form view.",
        "code": """
    @GetMapping("/owners/new")
    public String initCreationForm(Map<String, Object> model) {
        Owner owner = new Owner();
        model.put("owner", owner);
        return VIEWS_OWNER_CREATE_OR_UPDATE_FORM;
    }
        """,
        "context": {"static_facts": {"complexity": 1, "line_count": 6}},
    },
    {
        "name": "PetController.processCreationForm",
        "category": "Data Entry",
        "code": """
    @PostMapping("/pets/new")
    public String processCreationForm(Owner owner, @Valid Pet pet, BindingResult result, ModelMap model) {
        if (StringUtils.hasLength(pet.getName()) && pet.isNew() && owner.getPet(pet.getName(), true) != null) {
            result.rejectValue("name", "duplicate", "already exists");
        }
        owner.addPet(pet);
        if (result.hasErrors()) {
            model.put("pet", pet);
            return VIEWS_PETS_CREATE_OR_UPDATE_FORM;
        }
        this.owners.save(owner);
        return "redirect:/owners/" + owner.getId();
    }
        """,
        "context": {"static_facts": {"complexity": 4, "line_count": 13}},
        "reference": "processCreationForm validates that a pet name is not a duplicate, adds the pet to the owner, and redirects to the owner page on success or returns the form on validation errors.",
    },
    {
        "name": "VisitController.processNewVisitForm",
        "category": "Nested Logic",
        "code": """
    @PostMapping("/owners/{ownerId}/pets/{petId}/visits/new")
    public String processNewVisitForm(@Valid Visit visit, BindingResult result) {
        if (result.hasErrors()) {
            return "pets/createOrUpdateVisitForm";
        }
        this.visits.save(visit);
        return "redirect:/owners/{ownerId}";
    }
        """,
        "context": {"static_facts": {"complexity": 2, "line_count": 8}},
        "reference": "processNewVisitForm saves a new visit for a pet and redirects to the owner page, or returns the form view if there are binding errors.",
    },
    {
        "name": "CrashController.triggerException",
        "category": "Error Handling",
        "code": """
    @GetMapping("/oups")
    public String triggerException() {
        throw new RuntimeException(
                "Expected: controller used to showcase what " + "happens when an exception is thrown");
    }
        """,
        "context": {"static_facts": {"complexity": 1, "line_count": 5}},
        "reference": "triggerException deliberately throws a RuntimeException to demonstrate error handling behavior in Spring MVC.",
    },
    {
        "name": "OwnerController.processFindForm",
        "category": "Complex Data Flow",
        "code": """
    @GetMapping("/owners")
    public String processFindForm(Owner owner, BindingResult result, Map<String, Object> model) {
        if (owner.getLastName() == null) {
            owner.setLastName("");
        }
        Collection<Owner> results = this.owners.findByLastName(owner.getLastName());
        if (results.isEmpty()) {
            result.rejectValue("lastName", "notFound", "not found");
            return "owners/findOwners";
        } else if (results.size() == 1) {
            owner = results.iterator().next();
            return "redirect:/owners/" + owner.getId();
        } else {
            model.put("selections", results);
            return "owners/ownersList";
        }
    }
        """,
        "context": {"static_facts": {"complexity": 4, "line_count": 16}},
        "reference": "processFindForm searches for owners by last name. If no results are found it returns the search form. If exactly one owner is found it redirects to their details. Otherwise it displays a list.",
    },
]

# ---------------------------------------------------------------------------
# Ablation arms
# ---------------------------------------------------------------------------

ARMS = {
    "baseline": {
        "label": "LegacyLens (Baseline)",
        "repetition_variant": None,
    },
    "repetition_simple": {
        "label": "LegacyLens + Repetition (Simple)",
        "repetition_variant": "simple",
    },
    "repetition_verbose": {
        "label": "LegacyLens + Repetition (Verbose)",
        "repetition_variant": "verbose",
    },
    "repetition_x3": {
        "label": "LegacyLens + Repetition (x3)",
        "repetition_variant": "x3",
    },
}

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_arm(arm_name: str, arm_config: dict, functions: list) -> list[dict]:
    """Run a single ablation arm on all functions."""
    results = []
    label = arm_config["label"]
    rep_variant = arm_config["repetition_variant"]

    print(f"\n{'='*60}")
    print(f"ARM: {label}")
    print(f"{'='*60}")

    for fn in functions:
        name = fn["name"]
        print(f"  {name} ...", end=" ", flush=True)

        try:
            res = generate_verified_explanation(
                code=fn["code"],
                context=fn["context"],
                max_iterations=3,
                run_regeneration=True,
                language="java",
                repetition_variant=rep_variant,
            )

            row = {
                "arm": arm_name,
                "arm_label": label,
                "function": name,
                "category": fn["category"],
                "verified": res.verified,
                "confidence": res.confidence,
                "fidelity": res.fidelity_score,
                "iterations": res.iterations,
                "verdict": res.verdict,
                "hallucination_free": res.critique.factual_passed if res.critique else None,
                "completeness_pct": res.critique.completeness_pct if res.critique else None,
            }
            # BLEU/ROUGE vs reference annotation
            ref = fn.get("reference", "")
            if ref and res.explanation:
                nlp_scores = score_explanation(res.explanation, ref)
                row.update(nlp_scores)
            status = "✓" if res.verified else "✗"
            fid = f"{res.fidelity_score:.0%}" if res.fidelity_score else "N/A"
            r1 = f"{row.get('rouge1', 0):.2f}"
            print(f"{status} conf={res.confidence}% fid={fid} rouge1={r1}")

        except Exception as e:
            row = {
                "arm": arm_name,
                "arm_label": label,
                "function": name,
                "category": fn["category"],
                "verified": False,
                "confidence": 0,
                "fidelity": None,
                "iterations": 0,
                "verdict": "ERROR",
                "hallucination_free": None,
                "completeness_pct": None,
                "error": str(e),
            }
            print(f"ERROR: {e}")

        results.append(row)

    return results


def compute_summary(results: list[dict]) -> dict:
    """Compute aggregate metrics for an arm."""
    valid = [r for r in results if r["verdict"] != "ERROR"]
    if not valid:
        return {"count": 0}

    accuracies = [1 if r["verified"] else 0 for r in valid]
    halluc_free = [1 if r.get("hallucination_free") else 0 for r in valid]
    fidelities = [r["fidelity"] for r in valid if r["fidelity"] is not None]
    completeness = [r["completeness_pct"] for r in valid if r["completeness_pct"] is not None]
    bleu1s = [r["bleu1"] for r in valid if "bleu1" in r]
    rouge1s = [r["rouge1"] for r in valid if "rouge1" in r]
    rougeLs = [r["rougeL"] for r in valid if "rougeL" in r]

    def avg(lst): return sum(lst) / len(lst) if lst else 0.0

    return {
        "count": len(valid),
        "accuracy": avg([1 if r["verified"] else 0 for r in valid]),
        "hallucination_rate": 1 - avg(halluc_free),
        "avg_fidelity": avg(fidelities),
        "avg_completeness": avg(completeness),
        "avg_confidence": avg([r["confidence"] for r in valid]),
        "avg_bleu1": avg(bleu1s),
        "avg_rouge1": avg(rouge1s),
        "avg_rougeL": avg(rougeLs),
    }


def save_csv(all_results: list[dict], path: Path):
    """Save raw results to CSV."""
    if not all_results:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = all_results[0].keys()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nCSV saved: {path}")


def save_summary_md(summaries: dict, path: Path):
    """Save summary table as markdown for thesis."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("# Ablation Study Results\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
        f.write("| Method | Accuracy | Halluc↓ | Fidelity | Completeness | BLEU-1 | ROUGE-1 | ROUGE-L |\n")
        f.write("|--------|----------|---------|----------|-------------|--------|---------|---------|\n")

        for arm_name, summary in summaries.items():
            if summary["count"] == 0:
                continue
            label = ARMS[arm_name]["label"]
            f.write(
                f"| {label} "
                f"| {summary['accuracy']:.2f} "
                f"| {summary['hallucination_rate']:.2f} "
                f"| {summary['avg_fidelity']:.0%} "
                f"| {summary['avg_completeness']:.0f}% "
                f"| {summary.get('avg_bleu1', 0):.3f} "
                f"| {summary.get('avg_rouge1', 0):.3f} "
                f"| {summary.get('avg_rougeL', 0):.3f} |\n"
            )

        f.write(f"\n*Corpus: {len(FUNCTIONS)} PetClinic functions | References: hand-written 1-sentence summaries*\n")
    print(f"Summary saved: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LegacyLens Ablation Study")
    parser.add_argument(
        "--arms",
        default=",".join(ARMS.keys()),
        help=f"Comma-separated arms to run (available: {', '.join(ARMS.keys())})",
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Output directory for results (default: results/)",
    )
    args = parser.parse_args()

    selected = [a.strip() for a in args.arms.split(",")]
    for arm in selected:
        if arm not in ARMS:
            print(f"Unknown arm: {arm}. Available: {', '.join(ARMS.keys())}")
            sys.exit(1)

    provider = os.environ.get("LLM_PROVIDER", "local")
    print(f"LLM Provider: {provider}")
    print(f"Arms to run: {', '.join(selected)}")
    print(f"Test corpus: {len(FUNCTIONS)} functions")

    all_results = []
    summaries = {}

    for arm_name in selected:
        arm_results = run_arm(arm_name, ARMS[arm_name], FUNCTIONS)
        all_results.extend(arm_results)
        summaries[arm_name] = compute_summary(arm_results)

    # Save outputs
    out = Path(args.output_dir)
    save_csv(all_results, out / "ablation_results.csv")
    save_summary_md(summaries, out / "ablation_summary.md")

    # Print console summary
    print(f"\n{'='*60}")
    print("ABLATION SUMMARY")
    print(f"{'='*60}")
    for arm_name, s in summaries.items():
        if s["count"] == 0:
            continue
        label = ARMS[arm_name]["label"]
        print(
            f"  {label:40s} | "
            f"Acc={s['accuracy']:.2f} "
            f"Halluc={s['hallucination_rate']:.2f} "
            f"Fid={s['avg_fidelity']:.0%} "
            f"Comp={s['avg_completeness']:.0f}%"
        )


if __name__ == "__main__":
    main()
