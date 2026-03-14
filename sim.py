from legacylens.analysis.regeneration_validator import compute_ast_similarity
import sys
import pathlib

orig = pathlib.Path('scripts/faculty_demo.py').read_text()
# wait, what's original? let's extract it.
code = """
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

regen = pathlib.Path('debug_regen.java').read_text()

fid = compute_ast_similarity(code, regen, "java")
print("FIDELITY IS:", fid)
