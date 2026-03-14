@GetMapping("/owners")
public String processFindForm(@RequestParam(defaultValue = "1") int page, Owner owner, BindingResult result, Model model) {
    if (owner.getLastName() == null) {
        owner.setLastName(""); // Broad search for no last name input
    }
    
    List<Owner> ownersResults = findPaginatedForOwnersLastName(page, owner.getLastName());
    
    if (ownersResults.isEmpty()) {
        result.rejectValue("lastName", "notFound"); // No results found
        return "owners/findOwners"; 
    } else {
        model.addAttribute("owners", ownersResults);
        addPaginationModel(model, page, ownersResults);
        
        if (ownersResults.size() == 1) {
            Owner theOwner = ownersResults.get(0);
            return "redirect:/owners/" + theOwner.getId(); // Redirect to specific owner detail page
        } else {
            return "owners/findOwners"; 
        }
    }
}