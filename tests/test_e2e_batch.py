"""Step 12: 5-Function E2E Batch Validation.

Running the full LegacyLens pipeline (Writer -> Critic -> Regeneration)
on 5 diverse PetClinic functions to prove robustness.

Functions:
1. OwnerController.initCreationForm (Simple UI view)
2. PetController.processCreationForm (Data entry, validation)
3. VisitController.processNewVisitForm (Nested logic)
4. CrashController.triggerException (Error handling)
5. OwnerController.processFindForm (Complex data flow)
"""

import sys
import os
import json
from pathlib import Path

# Ensure project root is in path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from legacylens.agents.orchestrator import generate_verified_explanation

# --- Test Data ---

FUNCTIONS = [
    {
        "name": "OwnerController.initCreationForm",
        "category": "Simple View",
        "code": """
    @GetMapping("/owners/new")
    public String initCreationForm(Map<String, Object> model) {
        Owner owner = new Owner();
        model.put("owner", owner);
        return VIEWS_OWNER_CREATE_OR_UPDATE_FORM;
    }
        """,
        "context": {"static_facts": {"complexity": 1, "line_count": 6}}
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
        "context": {"static_facts": {"complexity": 4, "line_count": 13}}
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
        "context": {"static_facts": {"complexity": 2, "line_count": 8}}
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
        "context": {"static_facts": {"complexity": 1, "line_count": 5}}
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
        "context": {"static_facts": {"complexity": 4, "line_count": 16}}
    }
]

def run_test():
    print("Running 5-Function E2E Batch Validation...\n")
    
    # Force Groq provider
    os.environ["LLM_PROVIDER"] = "groq"
    
    results = []
    
    for fn in FUNCTIONS:
        print(f"Testing: {fn['name']} ({fn['category']})...")
        
        try:
            res = generate_verified_explanation(
                code=fn["code"],
                context=fn["context"],
                max_iterations=2,
                run_regeneration=True,
                language="java"
            )
            
            results.append({
                "name": fn["name"],
                "category": fn["category"],
                "verified": res.verified,
                "confidence": res.confidence,
                "fidelity": res.fidelity_score,
                "iterations": res.iterations,
                "status": "PASS" if res.verified else "FAIL"
            })
            print(f"  -> {res.status_string}\n")
            
        except Exception as e:
            print(f"  -> ERROR: {e}\n")
            results.append({
                "name": fn["name"],
                "category": fn["category"],
                "status": "ERROR",
                "details": str(e)
            })

    # Generate Markdown Report
    report_path = "e2e_validation_results.md"
    with open(report_path, "w") as f:
        f.write("# E2E Validation Results (Phase 1 Evaluation)\n\n")
        f.write("| Function | Category | Verified | Conf. | Fidelity | Result |\n")
        f.write("|:---|:---|:---:|:---:|:---:|:---:|\n")
        
        passed_count = 0
        for r in results:
            if r["status"] == "PASS":
                passed_count += 1
                icon = "✅"
            else:
                icon = "❌"
            
            fid = f"{r.get('fidelity', 0):.2f}" if r.get('fidelity') is not None else "N/A"
            conf = f"{r.get('confidence', 0)}%"
            
            f.write(f"| {r['name']} | {r['category']} | {r.get('verified')} | {conf} | {fid} | {icon} |\n")
            
        f.write(f"\n**Total Passed:** {passed_count}/{len(results)}\n")
    
    print(f"Validation complete. Report written to {report_path}")
    print(f"Passed: {passed_count}/{len(results)}")
    
    if passed_count == len(results):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_test()
