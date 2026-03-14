from legacylens.analysis.regeneration_validator import _get_parser, _flatten_ast
import pathlib

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
regen = pathlib.Path('debug_ext.txt').read_text()

parser = _get_parser("java")
tree_code = parser.parse(code.encode("utf-8"))
tree_regen = parser.parse(regen.encode("utf-8"))

print(len(_flatten_ast(tree_code.root_node)))
print(len(_flatten_ast(tree_regen.root_node)))
print("REGEN AST:")
print(tree_regen.root_node.sexp())

