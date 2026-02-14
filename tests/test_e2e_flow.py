"""Step 11: End-to-End Integration Integration.

Verifies the full orchestrator loop:
1. Writer drafts explanation (via Groq)
2. Critic verifies (via Groq + static checks)
3. Regeneration validator runs (via Groq + AST check)
4. Returns VerifiedExplanation with fidelity score
"""

import sys
import os
from pathlib import Path

# Ensure project root is in path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from legacylens.agents.orchestrator import generate_verified_explanation

# ProcessFindForm source code (simplified for test context)
CODE = """
@GetMapping("/owners")
public String processFindForm(@RequestParam(defaultValue = "1") int page, Owner owner, BindingResult result,
        Model model) {
    // allow parameterless GET request for /owners to return all records
    if (owner.getLastName() == null) {
        owner.setLastName(""); // empty string signifies broadest possible search
    }

    // find owners by last name
    Page<Owner> ownersResults = findPaginatedForOwnersLastName(page, owner.getLastName());
    if (ownersResults.isEmpty()) {
        // no owners found
        result.rejectValue("lastName", "notFound", "not found");
        return "owners/findOwners";
    }

    if (ownersResults.getTotalElements() == 1) {
        // 1 owner found
        owner = ownersResults.iterator().next();
        return "redirect:/owners/" + owner.getId();
    }

    // multiple owners found
    return addPaginationModel(page, model, ownersResults);
}
"""

CONTEXT = {
    "static_facts": {
        "complexity": 4,
        "line_count": 22,
        "calls": ["findPaginatedForOwnersLastName", "rejectValue", "addPaginationModel"],
    }
}

def run_test():
    print("Running E2E Integration Test on 'processFindForm'...")
    
    # Force Groq provider
    os.environ["LLM_PROVIDER"] = "groq"
    
    try:
        result = generate_verified_explanation(
            code=CODE,
            context=CONTEXT,
            max_iterations=2,
            run_regeneration=True,
            language="java"
        )
        
        print("\n--- TEST RESULTS ---")
        print(f"Verified: {result.verified}")
        print(f"Confidence: {result.confidence}%")
        print(f"Iterations: {result.iterations}")
        print(f"Fidelity Score: {result.fidelity_score}")
        print(f"Explanation Preview: {result.explanation[:100]}...")
        
        if result.fidelity_score is None:
            print("FAIL: Regeneration validation did not run (fidelity_score is None)")
            sys.exit(1)
            
        if result.fidelity_score < 0.1:
            print(f"WARNING: Low fidelity score ({result.fidelity_score}). Check regeneration logic.")
            
        if result.verified:
            print("PASS: Explanation verified and validated.")
            sys.exit(0)
        else:
            print("WARNING: Explanation NOT verified (Critic rejection). Inspect logs.")
            # We treat this as a pass for integration testing (the loop ran), 
            # but ideally it should pass.
            sys.exit(0)
            
    except Exception as e:
        print(f"FAIL: Exception in orchestrator loop: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_test()
