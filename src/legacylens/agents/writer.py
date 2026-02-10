"""Writer Agent - Generates explanation drafts.

Uses a compact prompt to minimize token count and inference time.
"""

import ollama


def write_explanation(
    code: str,
    context: dict,
    model: str = "deepseek-coder:6.7b",
) -> str:
    """
    Generate an explanation draft for the given code.

    Args:
        code: The source code to explain
        context: Dict with static_facts, callers, callees
        model: Ollama model to use

    Returns:
        Explanation text
    """
    # Build compact facts line
    sf = context.get("static_facts", {})
    facts_parts = []
    if sf.get("complexity"):
        facts_parts.append(f"complexity={sf['complexity']}")
    if sf.get("line_count"):
        facts_parts.append(f"lines={sf['line_count']}")
    if sf.get("calls"):
        calls = sf["calls"][:3]  # Max 3
        if calls:
            facts_parts.append(f"calls={','.join(calls)}")

    facts_line = " | ".join(facts_parts) if facts_parts else "n/a"

    # Include revision feedback if retrying
    revision = ""
    if context.get("revision_feedback"):
        revision = f"\nFIX THESE ISSUES: {context['revision_feedback']}\n"

    prompt = f"""Explain this code concisely. Reference the analysis facts.
{revision}
CODE:
{code}

FACTS: {facts_line}

EXPLANATION:"""

    try:
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={
                "temperature": 0.3,
                "num_predict": 300,  # Cap output length
            },
        )
        return response["response"].strip()
    except Exception as e:
        return f"[Writer Error: {e}]"
