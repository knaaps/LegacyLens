import sys
from legacylens.analysis.regeneration_validator import _get_parser, _flatten_ast, compute_ast_similarity

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

code2 = """
class Foo {
""" + code + """
}
"""
fid = compute_ast_similarity(code, code2, "java")
print("FIDELITY WITH WRAPPER: ", fid)

fid2 = compute_ast_similarity(code, code, "java")
print("FIDELITY SAME: ", fid2)
