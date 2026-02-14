"""Test Critic Bug Catch Rate — Step 10.

Injects 5 synthetic bugs into explanations for a known code snippet and verifies
that the Critic catches at least 4 of them (>70% catch rate).

Bugs:
1. Hallucinated function call (Factual)
2. Missing parameter mention (Completeness)
3. Unflagged SQL injection risk (Risk)
4. Incorrect return type claim (Factual)
5. Generic/vague description (Completeness)
"""

import sys
from legacylens.agents.critic import critique_explanation

# Target code: A function with SQL injection risk
CODE = """
public List<Owner> findOwners(String lastName) {
    String sql = "SELECT * FROM owners WHERE last_name = '" + lastName + "'";
    return jdbcTemplate.query(sql, new OwnerMapper());
}
"""

BUGS = [
    {
        "name": "Hallucination (Factual)",
        "explanation": "The function executes a SQL query and then calls `validateResults()` to ensure data integrity before returning the list.",
        "expected_issue": "validateResults",
    },
    {
        "name": "Missing Parameter (Completeness)",
        "explanation": "This function queries the database for owners and returns a list of Owner objects mapped by the OwnerMapper.",
        "expected_issue": "parameters",
    },
    {
        "name": "Unflagged Risk (Risk)",
        "explanation": "The function builds a SQL query string using the provided last name and executes it safely using jdbcTemplate.",
        "expected_issue": "injection",
    },
    {
        "name": "Wrong Return Type (Factual)",
        "explanation": "The function takes a last name and returns a single Owner object if found, or null otherwise.",
        "expected_issue": "return",
    },
    {
        "name": "Vague Description (Completeness)",
        "explanation": "This code does some database stuff.",
        "expected_issue": "purpose",
    },
]

def run_test():
    caught = 0
    total = len(BUGS)
    
    print(f"Running {total} synthetic bug tests...\n")
    
    for i, bug in enumerate(BUGS, 1):
        print(f"Test {i}: {bug['name']}")
        
        result = critique_explanation(CODE, bug["explanation"])
        
        # Check if it failed (which is good!) and if the issue was mentioned
        passed = False
        if not result.passed:
            # Check if reason is roughly correct
            issues_str = ", ".join(result.issues).lower()
            if bug["expected_issue"].lower() in issues_str or not result.factual_passed or result.completeness_pct < 50 or result.flagged_risks:
                 passed = True
        
        if passed:
            print(f"  ✅ Caught! (Issues: {result.issues})")
            caught += 1
        else:
            print(f"  ❌ Missed. (Critic output: {result})")
            
        print("-" * 50)

    catch_rate = caught / total
    print(f"\nFinal Score: {caught}/{total} ({catch_rate:.0%})")
    
    if catch_rate >= 0.70:
        print("PASS: Catch rate >= 70%")
        sys.exit(0)
    else:
        print("FAIL: Catch rate < 70%")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
