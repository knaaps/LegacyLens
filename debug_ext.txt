@GetMapping("/owners")
public String processFindForm(@RequestParam(defaultValue = "1") int page, Owner owner, BindingResult result, Model model) {
    if (owner == null || owner.getLastName() == null || owner.getLastName().isEmpty()) {
        return "owners/findOwners"; // Return search form with errors/results
    }
    
    List<Owner> owners = ownerRepository.findByLastName(owner.getLastName());
    if (owners == null || owners.isEmpty()) {
        result.rejectValue("lastName", "notFound"); // Adds a validation error to BindingResult and redisplays the form
        return "owners/findOwners"; 
    } else if (owners.size() > 1) {
        addPaginationModel(model, page, owners); // Modifies model with paginated data via addPaginationModel method
        return "owners/list"; // Returns paginated results view
    } else {
        Owner foundOwner = owners.get(0);
        model.addAttribute("owner", foundOwner); // Adds the owner to the model for display in the details view
        return "redirect:/owners/" + foundOwner.getId(); // Triggers a redirect (URL change) when a single owner is found
    }
}