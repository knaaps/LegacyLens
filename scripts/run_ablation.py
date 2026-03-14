"""Ablation Study Runner — Compare LegacyLens configurations on a mixed corpus.

Runs the full pipeline (Writer → Critic → Regeneration) on a corpus of
PetClinic + legacy-style Java functions under multiple configurations:

  ARM 1 — zero_shot:          Plain LLM call, no context, no critic, no regen
  ARM 2 — rag_only:           RAG-style context, no critic, no regen
  ARM 3 — baseline:           Full LegacyLens pipeline, no prompt repetition
  ARM 4 — repetition_simple:  Baseline + Leviathan simple repetition
  ARM 5 — repetition_verbose: Baseline + verbose repetition
  ARM 6 — repetition_x3:      Baseline + x3 repetition (strongest)

Usage:
    # Full study (Groq recommended for speed)
    LLM_PROVIDER=groq python3 scripts/run_ablation.py

    # Specific arms only
    LLM_PROVIDER=groq python3 scripts/run_ablation.py --arms zero_shot,baseline,repetition_x3

Output:
    results/ablation_results.csv   — raw per-function scores
    results/ablation_summary.md    — markdown table for thesis
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from legacylens.agents.orchestrator import generate_verified_explanation
from legacylens.agents.provider import llm_generate

# Import BLEU/ROUGE scorer (same scripts/ directory, no extra deps)
sys.path.insert(0, str(Path(__file__).parent))
from metrics_scorer import score_explanation

# ---------------------------------------------------------------------------
# Test corpus — 10 PetClinic + 3 Apache Ant-style functions
# Gold references: one precise sentence covering purpose, params, flow, returns.
# ---------------------------------------------------------------------------

FUNCTIONS = [
    # ── PetClinic: OwnerController ───────────────────────────────────────────
    {
        "name": "OwnerController.initCreationForm",
        "category": "Simple View",
        "reference": (
            "initCreationForm handles GET /owners/new and returns the owner "
            "creation form view name; since Spring MVC injects a blank Owner "
            "via the @ModelAttribute findOwner method, no logic is needed here."
        ),
        "code": """
    @GetMapping("/owners/new")
    public String initCreationForm() {
        return VIEWS_OWNER_CREATE_OR_UPDATE_FORM;
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 1,
                "line_count": 3,
                "calls": [],
                "field_reads": [],
                "field_writes": [],
            }
        },
    },
    {
        "name": "OwnerController.processCreationForm",
        "category": "Data Entry",
        "reference": (
            "processCreationForm handles POST /owners/new: validates the owner "
            "with @Valid, persists via owners.save() on success and redirects to "
            "the owner detail page, or returns the form view with a flash error "
            "message if BindingResult has errors."
        ),
        "code": """
    @PostMapping("/owners/new")
    public String processCreationForm(@Valid Owner owner, BindingResult result, RedirectAttributes redirectAttributes) {
        if (result.hasErrors()) {
            redirectAttributes.addFlashAttribute("error", "There was an error in creating the owner.");
            return VIEWS_OWNER_CREATE_OR_UPDATE_FORM;
        }
        this.owners.save(owner);
        redirectAttributes.addFlashAttribute("message", "New Owner Created");
        return "redirect:/owners/" + owner.getId();
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 2,
                "line_count": 9,
                "calls": ["save"],
                "field_reads": [],
                "field_writes": [],
            }
        },
    },
    {
        "name": "OwnerController.processFindForm",
        "category": "Complex Data Flow",
        "reference": (
            "processFindForm handles GET /owners and searches owners by last name "
            "(defaulting to empty string for all owners); if no match is found it "
            "rejects the lastName field and re-shows the search form, if exactly "
            "one owner matches it redirects to that owner's detail page, and if "
            "multiple match it delegates to addPaginationModel for a paginated list."
        ),
        "code": """
    @GetMapping("/owners")
    public String processFindForm(@RequestParam(defaultValue = "1") int page, Owner owner,
            BindingResult result, Model model) {
        String lastName = owner.getLastName();
        if (lastName == null) {
            lastName = "";
        }
        Page<Owner> ownersResults = findPaginatedForOwnersLastName(page, lastName);
        if (ownersResults.isEmpty()) {
            result.rejectValue("lastName", "notFound", "not found");
            return "owners/findOwners";
        }
        if (ownersResults.getTotalElements() == 1) {
            owner = ownersResults.iterator().next();
            return "redirect:/owners/" + owner.getId();
        }
        return addPaginationModel(page, model, ownersResults);
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 5,
                "line_count": 17,
                "calls": ["findPaginatedForOwnersLastName", "addPaginationModel"],
                "field_reads": [],
                "field_writes": [],
            }
        },
    },
    {
        "name": "OwnerController.processUpdateOwnerForm",
        "category": "Update — ID Validation",
        "reference": (
            "processUpdateOwnerForm handles POST /owners/{ownerId}/edit: validates "
            "the owner with @Valid, checks that the form owner ID matches the URL "
            "path variable (rejecting mismatches with a flash error), sets the ID, "
            "saves the owner, and redirects to the owner detail page."
        ),
        "code": """
    @PostMapping("/owners/{ownerId}/edit")
    public String processUpdateOwnerForm(@Valid Owner owner, BindingResult result,
            @PathVariable("ownerId") int ownerId, RedirectAttributes redirectAttributes) {
        if (result.hasErrors()) {
            redirectAttributes.addFlashAttribute("error", "There was an error in updating the owner.");
            return VIEWS_OWNER_CREATE_OR_UPDATE_FORM;
        }
        if (!Objects.equals(owner.getId(), ownerId)) {
            result.rejectValue("id", "mismatch", "The owner ID in the form does not match the URL.");
            redirectAttributes.addFlashAttribute("error", "Owner ID mismatch. Please try again.");
            return "redirect:/owners/{ownerId}/edit";
        }
        owner.setId(ownerId);
        this.owners.save(owner);
        redirectAttributes.addFlashAttribute("message", "Owner Values Updated");
        return "redirect:/owners/{ownerId}";
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 4,
                "line_count": 17,
                "calls": ["equals", "save"],
                "field_reads": [],
                "field_writes": [],
            }
        },
    },
    {
        "name": "OwnerController.showOwner",
        "category": "Detail View",
        "reference": (
            "showOwner handles GET /owners/{ownerId} and returns a ModelAndView "
            "populated with the Owner fetched by ID from the repository; it throws "
            "an IllegalArgumentException if the owner is not found."
        ),
        "code": """
    @GetMapping("/owners/{ownerId}")
    public ModelAndView showOwner(@PathVariable("ownerId") int ownerId) {
        ModelAndView mav = new ModelAndView("owners/ownerDetails");
        Optional<Owner> optionalOwner = this.owners.findById(ownerId);
        Owner owner = optionalOwner.orElseThrow(() -> new IllegalArgumentException(
                "Owner not found with id: " + ownerId + ". Please ensure the ID is correct "));
        mav.addObject(owner);
        return mav;
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 2,
                "line_count": 8,
                "calls": ["findById", "orElseThrow", "addObject"],
                "field_reads": [],
                "field_writes": [],
            }
        },
    },
    # ── PetClinic: PetController ─────────────────────────────────────────────
    {
        "name": "PetController.processCreationForm",
        "category": "Data Entry — Duplicate Check",
        "reference": (
            "processCreationForm handles POST /owners/{ownerId}/pets/new: it rejects "
            "duplicate pet names and future birth dates via BindingResult, then adds "
            "the pet to the owner and persists via owners.save() on success, "
            "redirecting to the owner page."
        ),
        "code": """
    @PostMapping("/pets/new")
    public String processCreationForm(Owner owner, @Valid Pet pet, BindingResult result,
            RedirectAttributes redirectAttributes) {
        if (StringUtils.hasText(pet.getName()) && pet.isNew() && owner.getPet(pet.getName(), true) != null)
            result.rejectValue("name", "duplicate", "already exists");
        LocalDate currentDate = LocalDate.now();
        if (pet.getBirthDate() != null && pet.getBirthDate().isAfter(currentDate)) {
            result.rejectValue("birthDate", "typeMismatch.birthDate");
        }
        if (result.hasErrors()) {
            return VIEWS_PETS_CREATE_OR_UPDATE_FORM;
        }
        owner.addPet(pet);
        this.owners.save(owner);
        redirectAttributes.addFlashAttribute("message", "New Pet has been Added");
        return "redirect:/owners/{ownerId}";
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 5,
                "line_count": 16,
                "calls": [
                    "hasText",
                    "isNew",
                    "getPet",
                    "now",
                    "isAfter",
                    "rejectValue",
                    "hasErrors",
                    "addPet",
                    "save",
                ],
                "field_reads": [],
                "field_writes": [],
            }
        },
    },
    {
        "name": "PetController.processUpdateForm",
        "category": "Update — Name/Date Validation",
        "reference": (
            "processUpdateForm handles POST /owners/{ownerId}/pets/{petId}/edit: "
            "it checks for a duplicate pet name (excluding the current pet by ID), "
            "rejects future birth dates, delegates to updatePetDetails on success, "
            "and redirects to the owner page."
        ),
        "code": """
    @PostMapping("/pets/{petId}/edit")
    public String processUpdateForm(Owner owner, @Valid Pet pet, BindingResult result,
            RedirectAttributes redirectAttributes) {
        String petName = pet.getName();
        if (StringUtils.hasText(petName)) {
            Pet existingPet = owner.getPet(petName, false);
            if (existingPet != null && !Objects.equals(existingPet.getId(), pet.getId())) {
                result.rejectValue("name", "duplicate", "already exists");
            }
        }
        LocalDate currentDate = LocalDate.now();
        if (pet.getBirthDate() != null && pet.getBirthDate().isAfter(currentDate)) {
            result.rejectValue("birthDate", "typeMismatch.birthDate");
        }
        if (result.hasErrors()) {
            return VIEWS_PETS_CREATE_OR_UPDATE_FORM;
        }
        updatePetDetails(owner, pet);
        redirectAttributes.addFlashAttribute("message", "Pet details has been edited");
        return "redirect:/owners/{ownerId}";
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 6,
                "line_count": 19,
                "calls": [
                    "hasText",
                    "getPet",
                    "equals",
                    "getId",
                    "rejectValue",
                    "now",
                    "isAfter",
                    "hasErrors",
                    "updatePetDetails",
                ],
                "field_reads": [],
                "field_writes": [],
            }
        },
    },
    # ── PetClinic: VetController ─────────────────────────────────────────────
    {
        "name": "VetController.showVetList",
        "category": "Paginated View",
        "reference": (
            "showVetList handles GET /vets.html with an optional page parameter "
            "(default 1): it loads a paginated page of Vet objects, wraps them in "
            "a Vets container, and delegates to addPaginationModel to populate the "
            "model and return the vet list view name."
        ),
        "code": """
    @GetMapping("/vets.html")
    public String showVetList(@RequestParam(defaultValue = "1") int page, Model model) {
        Vets vets = new Vets();
        Page<Vet> paginated = findPaginated(page);
        vets.getVetList().addAll(paginated.toList());
        return addPaginationModel(page, paginated, model);
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 1,
                "line_count": 6,
                "calls": ["findPaginated", "getVetList", "addAll", "toList", "addPaginationModel"],
                "field_reads": [],
                "field_writes": [],
            }
        },
    },
    {
        "name": "VetController.showResourcesVetList",
        "category": "REST Endpoint",
        "reference": (
            "showResourcesVetList handles GET /vets and returns all vets as a "
            "@ResponseBody Vets JSON object by loading all records from the "
            "repository and populating a Vets container."
        ),
        "code": """
    @GetMapping({ "/vets" })
    public @ResponseBody Vets showResourcesVetList() {
        Vets vets = new Vets();
        vets.getVetList().addAll(this.vetRepository.findAll());
        return vets;
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 1,
                "line_count": 5,
                "calls": ["getVetList", "addAll", "findAll"],
                "field_reads": [],
                "field_writes": [],
            }
        },
    },
    # ── PetClinic: Owner domain object ───────────────────────────────────────
    {
        "name": "Owner.addVisit",
        "category": "Domain Logic",
        "reference": (
            "addVisit adds a Visit to the Pet identified by petId within this Owner: "
            "it asserts that neither petId nor visit is null using Assert.notNull, "
            "retrieves the pet by ID (asserting it exists), and calls pet.addVisit(visit)."
        ),
        "code": """
    public void addVisit(Integer petId, Visit visit) {
        Assert.notNull(petId, "Pet identifier must not be null!");
        Assert.notNull(visit, "Visit must not be null!");
        Pet pet = getPet(petId);
        Assert.notNull(pet, "Invalid Pet identifier!");
        pet.addVisit(visit);
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 1,
                "line_count": 7,
                "calls": ["notNull", "getPet", "addVisit"],
                "field_reads": ["pets"],
                "field_writes": [],
            }
        },
    },
    # ── Apache Ant-style legacy patterns ─────────────────────────────────────
    {
        "name": "AntTask.execute",
        "category": "Legacy — Build Task",
        "reference": (
            "execute is the main entry point for an Ant task: it validates that the "
            "required 'srcdir' attribute is set, iterates over all .java files in "
            "the source directory, and delegates compilation to compileFile for each; "
            "it throws a BuildException if srcdir is null."
        ),
        "code": """
    public void execute() throws BuildException {
        if (srcdir == null) {
            throw new BuildException("srcdir attribute must be set", getLocation());
        }
        String[] files = srcdir.list();
        for (String file : files) {
            if (file.endsWith(".java")) {
                compileFile(new File(srcdir, file));
            }
        }
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 4,
                "line_count": 10,
                "calls": ["list", "endsWith", "compileFile"],
                "field_reads": ["srcdir"],
                "field_writes": [],
            }
        },
    },
    {
        "name": "AntTask.compileFile",
        "category": "Legacy — File Processing",
        "reference": (
            "compileFile opens a FileInputStream on the given source file, compiles "
            "it by reading bytes into a buffer in a loop, and writes output to the "
            "destination; resource management relies on explicit close() calls in a "
            "finally block rather than try-with-resources, a legacy pattern that "
            "risks resource leaks on exceptions."
        ),
        "code": """
    private void compileFile(File sourceFile) throws BuildException {
        FileInputStream fis = null;
        try {
            fis = new FileInputStream(sourceFile);
            byte[] buffer = new byte[1024];
            int bytesRead;
            while ((bytesRead = fis.read(buffer)) != -1) {
                outputStream.write(buffer, 0, bytesRead);
            }
        } catch (Exception e) {
            throw new BuildException("Compilation failed for: " + sourceFile.getName());
        } finally {
            if (fis != null) {
                try { fis.close(); } catch (Exception ignore) {}
            }
        }
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 5,
                "line_count": 17,
                "calls": ["read", "write", "close"],
                "field_reads": ["outputStream"],
                "field_writes": [],
            }
        },
    },
    {
        "name": "AntTask.log",
        "category": "Legacy — Logging",
        "reference": (
            "log writes a formatted message to System.out with a timestamp prefix "
            "and the given message; it uses string concatenation (not a logging "
            "framework) and offers no thread-safety guarantees, a common legacy "
            "anti-pattern."
        ),
        "code": """
    protected void log(String message) {
        String timestamp = new java.text.SimpleDateFormat("HH:mm:ss").format(new java.util.Date());
        System.out.println("[" + timestamp + "] " + message);
    }
        """,
        "context": {
            "static_facts": {
                "complexity": 1,
                "line_count": 4,
                "calls": ["format", "println"],
                "field_reads": [],
                "field_writes": [],
            }
        },
    },
]

# ---------------------------------------------------------------------------
# Ablation arms
# ---------------------------------------------------------------------------

ARMS = {
    "zero_shot": {
        "label": "Zero-Shot (no context, no verification)",
        "repetition_variant": None,
        "_zero_shot": True,
    },
    "rag_only": {
        "label": "RAG-Only (semantic context, no verification)",
        "repetition_variant": None,
        "_rag_only": True,
    },
    "baseline": {
        "label": "LegacyLens (Full Pipeline, no repetition)",
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
# Zero-shot runner — single LLM call, no context, no critic
# ---------------------------------------------------------------------------


def run_zero_shot(fn: dict, writer_model: str = "deepseek-coder:6.7b") -> str:
    """Single prompt, no context, no verification."""
    prompt = (
        "You are a software engineer. Explain the following code clearly and concisely.\n\n"
        f"CODE:\n{fn['code']}\n\nEXPLANATION:"
    )
    return llm_generate(prompt=prompt, model=writer_model, temperature=0.3)


def run_rag_only(fn: dict, writer_model: str = "deepseek-coder:6.7b") -> str:
    """Single LLM call with code context only, no critic verification."""
    facts = fn.get("context", {}).get("static_facts", {})
    context_str = (
        f"Complexity: {facts.get('complexity', '?')}, Lines: {facts.get('line_count', '?')}"
    )
    prompt = (
        "You are a software engineer. Given the code and its static metrics, explain this function.\n\n"
        f"STATIC METRICS: {context_str}\n\n"
        f"CODE:\n{fn['code']}\n\nEXPLANATION:"
    )
    return llm_generate(prompt=prompt, model=writer_model, temperature=0.3)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_arm(arm_name: str, arm_config: dict, functions: list, writer_model: str) -> list[dict]:
    """Run a single ablation arm on all functions."""
    results = []
    label = arm_config["label"]
    rep_variant = arm_config.get("repetition_variant")
    is_zero_shot = arm_config.get("_zero_shot", False)
    is_rag_only = arm_config.get("_rag_only", False)

    print(f"\n{'=' * 70}")
    print(f"ARM: {label}")
    print(f"{'=' * 70}")

    for fn in functions:
        name = fn["name"]
        print(f"  {name} ...", end=" ", flush=True)

        try:
            if is_zero_shot:
                explanation = run_zero_shot(fn, writer_model=writer_model)
                row = {
                    "arm": arm_name,
                    "arm_label": label,
                    "function": name,
                    "category": fn["category"],
                    "verified": False,
                    "confidence": 0,
                    "fidelity": None,
                    "iterations": 1,
                    "verdict": "ZERO_SHOT",
                    "hallucination_free": None,
                    "completeness_pct": None,
                }

            elif is_rag_only:
                explanation = run_rag_only(fn, writer_model=writer_model)
                row = {
                    "arm": arm_name,
                    "arm_label": label,
                    "function": name,
                    "category": fn["category"],
                    "verified": False,
                    "confidence": 0,
                    "fidelity": None,
                    "iterations": 1,
                    "verdict": "RAG_ONLY",
                    "hallucination_free": None,
                    "completeness_pct": None,
                }

            else:
                res = generate_verified_explanation(
                    code=fn["code"],
                    context=fn["context"],
                    max_iterations=3,
                    run_regeneration=True,
                    run_finalizer=False,
                    language="java",
                    repetition_variant=rep_variant,
                    writer_model=writer_model,
                )
                explanation = res.explanation
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

            # BLEU/ROUGE vs gold reference
            ref = fn.get("reference", "")
            if ref and explanation:
                nlp_scores = score_explanation(explanation, ref)
                row.update(nlp_scores)

            fid = f"{row.get('fidelity', 0) or 0:.0%}" if row.get("fidelity") is not None else "N/A"
            r1 = f"{row.get('rouge1', 0):.2f}"
            print(f"✓ conf={row.get('confidence', 0)}% fid={fid} rouge1={r1}")

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


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def compute_summary(results: list[dict]) -> dict:
    """Compute aggregate metrics for an arm."""
    valid = [r for r in results if r["verdict"] not in ("ERROR",)]
    if not valid:
        return {"count": 0}

    def avg(lst):
        return sum(lst) / len(lst) if lst else 0.0

    halluc_free = [
        1 if r.get("hallucination_free") else 0
        for r in valid
        if r.get("hallucination_free") is not None
    ]
    fidelities = [r["fidelity"] for r in valid if r.get("fidelity") is not None]
    completeness = [r["completeness_pct"] for r in valid if r.get("completeness_pct") is not None]

    return {
        "count": len(valid),
        "accuracy": avg([1 if r["verified"] else 0 for r in valid]),
        "hallucination_rate": 1 - avg(halluc_free) if halluc_free else None,
        "avg_fidelity": avg(fidelities),
        "avg_completeness": avg(completeness),
        "avg_confidence": avg([r["confidence"] for r in valid]),
        "avg_bleu1": avg([r["bleu1"] for r in valid if "bleu1" in r]),
        "avg_bleu2": avg([r.get("bleu2", 0) for r in valid if "bleu2" in r]),
        "avg_rouge1": avg([r["rouge1"] for r in valid if "rouge1" in r]),
        "avg_rouge2": avg([r.get("rouge2", 0) for r in valid if "rouge2" in r]),
        "avg_rougeL": avg([r["rougeL"] for r in valid if "rougeL" in r]),
    }


# ---------------------------------------------------------------------------
# Saving outputs
# ---------------------------------------------------------------------------


def save_csv(all_results: list[dict], path: Path):
    """Save raw results to CSV."""
    if not all_results:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    all_keys: set = set()
    for r in all_results:
        all_keys.update(r.keys())
    ordered_keys = [
        "arm",
        "arm_label",
        "function",
        "category",
        "verified",
        "confidence",
        "fidelity",
        "iterations",
        "verdict",
        "hallucination_free",
        "completeness_pct",
        "bleu1",
        "bleu2",
        "rouge1",
        "rouge2",
        "rougeL",
        "error",
    ]
    fieldnames = [k for k in ordered_keys if k in all_keys] + [
        k for k in sorted(all_keys) if k not in ordered_keys
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nCSV saved: {path}")


def save_summary_md(summaries: dict, path: Path):
    """Save summary table as markdown for thesis."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n_funcs = len(FUNCTIONS)
    with open(path, "w") as f:
        f.write("# Ablation Study Results\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
        f.write(
            "| Method | Acc↑ | Halluc↓ | Fidelity↑ | Complete↑ | "
            "BLEU-1↑ | BLEU-2↑ | ROUGE-1↑ | ROUGE-L↑ |\n"
        )
        f.write(
            "|--------|------|---------|-----------|-----------|"
            "--------|--------|---------|----------|\n"
        )

        for arm_name, summary in summaries.items():
            if summary["count"] == 0:
                continue
            label = ARMS[arm_name]["label"]
            halluc = (
                f"{summary['hallucination_rate']:.2f}"
                if summary["hallucination_rate"] is not None
                else "N/A"
            )
            f.write(
                f"| {label} "
                f"| {summary['accuracy']:.2f} "
                f"| {halluc} "
                f"| {summary['avg_fidelity']:.0%} "
                f"| {summary['avg_completeness']:.0f}% "
                f"| {summary.get('avg_bleu1', 0):.3f} "
                f"| {summary.get('avg_bleu2', 0):.3f} "
                f"| {summary.get('avg_rouge1', 0):.3f} "
                f"| {summary.get('avg_rougeL', 0):.3f} |\n"
            )

        f.write(
            f"\n*Corpus: {n_funcs} functions "
            f"(10 Spring PetClinic + 3 Apache Ant-style legacy) "
            "| References: hand-written gold-standard summaries*\n"
        )
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
    parser.add_argument(
        "--writer-model",
        default="deepseek-coder:6.7b",
        help="Writer model (default: deepseek-coder:6.7b; auto-mapped for Groq)",
    )
    args = parser.parse_args()

    selected = [a.strip() for a in args.arms.split(",")]
    for arm in selected:
        if arm not in ARMS:
            print(f"Unknown arm: {arm}. Available: {', '.join(ARMS.keys())}")
            sys.exit(1)

    provider = os.environ.get("LLM_PROVIDER", "local")
    print(f"LLM Provider: {provider}")
    print(f"Writer model: {args.writer_model}")
    print(f"Arms to run: {', '.join(selected)}")
    print(f"Test corpus: {len(FUNCTIONS)} functions")

    all_results = []
    summaries = {}

    for arm_name in selected:
        arm_results = run_arm(arm_name, ARMS[arm_name], FUNCTIONS, args.writer_model)
        all_results.extend(arm_results)
        summaries[arm_name] = compute_summary(arm_results)

    # Save outputs
    out = Path(args.output_dir)
    save_csv(all_results, out / "ablation_results.csv")
    save_summary_md(summaries, out / "ablation_summary.md")

    # Print console summary
    print(f"\n{'=' * 70}")
    print("ABLATION SUMMARY")
    print(f"{'=' * 70}")
    for arm_name in selected:
        s = summaries.get(arm_name, {})
        if not s.get("count"):
            continue
        label = ARMS[arm_name]["label"]
        halluc = (
            f"Halluc={s['hallucination_rate']:.2f}"
            if s["hallucination_rate"] is not None
            else "Halluc=N/A"
        )
        print(
            f"  {label:50s} | "
            f"Acc={s['accuracy']:.2f} {halluc} "
            f"Fid={s['avg_fidelity']:.0%} "
            f"ROUGE1={s.get('avg_rouge1', 0):.3f}"
        )


if __name__ == "__main__":
    main()
