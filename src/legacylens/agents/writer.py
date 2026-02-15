"""Writer Agent — Generates explanation drafts.

The Writer uses a higher temperature (0.3) to produce fluent,
readable explanations while still staying grounded in the code.
"""

from legacylens.agents.provider import llm_generate


def write_explanation(
    code: str,
    context: dict,
    model: str = "deepseek-coder:6.7b",
) -> str:
    """
    Generate an explanation draft for the given code.

    Args:
        code: The source code to explain
        context: Dict containing static_facts, similar_code, etc.
        model: Model name (auto-mapped for Groq if LLM_PROVIDER=groq)

    Returns:
        Explanation text (may contain inaccuracies — needs verification)
    """
    # Build grounding facts from context
    facts = []
    static_facts = context.get("static_facts", {})

    if static_facts.get("complexity"):
        facts.append(f"Complexity: {static_facts['complexity']}")
    if static_facts.get("line_count"):
        facts.append(f"Lines: {static_facts['line_count']}")
    if static_facts.get("calls"):
        calls = static_facts["calls"]
        if calls:
            facts.append(f"Calls: {', '.join(calls[:5])}")

    # Include related code if available
    related_code = ""
    if context.get("callers"):
        related_code += "\n\n--- FUNCTIONS THAT CALL THIS ---\n"
        for caller in context["callers"][:2]:
            related_code += f"\n{caller}\n"

    if context.get("callees"):
        related_code += "\n\n--- FUNCTIONS THIS CALLS ---\n"
        for callee in context["callees"][:2]:
            related_code += f"\n{callee}\n"

    facts_text = "\n".join(f"• {f}" for f in facts) if facts else "None available"

    prompt = f"""You are an expert developer explaining code to a colleague.

TARGET CODE:
```
{code}
```

STATIC ANALYSIS FACTS:
{facts_text}
{related_code}

INSTRUCTIONS:
1. Explain the PURPOSE of this code in clear, simple terms
2. Describe the PARAMETERS it accepts and the RETURN value it produces
3. Note any ERROR HANDLING (exceptions, validation, edge cases)
4. Mention SIDE EFFECTS (what it modifies, saves, calls, or invokes)
5. Reference the static analysis facts where relevant
6. Keep it concise but complete

EXPLANATION:"""

    try:
        return llm_generate(prompt=prompt, model=model, temperature=0.3)
    except Exception as e:
        return f"[Writer Error: {e}]"
