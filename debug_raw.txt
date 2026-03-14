@GetMapping("/owners")
public String processFindForm(@RequestParam(defaultValue = "1") int page, Owner owner, BindingResult result, Model model) {
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
        return "redirect:/owners/" + owner.getId();
    }
    model.addAttribute("owners", ownersResults);
    addPaginationModel(page, model, ownersResults);
    return "owners/findOwners";
}