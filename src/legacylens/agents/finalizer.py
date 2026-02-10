"""Finalizer Agent - Polishes the verified explanation.

After the Writer→Critic loop produces a verified explanation,
the Finalizer formats it into a clean, structured output with
section headers and a summary line.

Uses the SAME model as Writer/Critic (stays warm in memory).
"""

import ollama


def finalize_explanation(
    explanation: str,
    static_facts: dict,
    safety_risk: str = "",
    model: str = "deepseek-coder:6.7b",
) -> str:
    """
    Polish a verified explanation into final output format.

    Args:
        explanation: The verified explanation text
        static_facts: Dict with name, file_path, complexity, etc.
        safety_risk: Safety concern from Critic (if any)
        model: Ollama model (same as Writer/Critic)

    Returns:
        Polished explanation with structure
    """
    name = static_facts.get("name", "unknown")
    safety_line = f"\nSAFETY WARNING: {safety_risk}" if safety_risk else ""

    prompt = f"""Reformat this code explanation into a clean, structured output.
Add brief section headers. Keep it concise. Do NOT add new information.
{safety_line}

FUNCTION: {name}
EXPLANATION:
{explanation}

FORMATTED OUTPUT:"""

    try:
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={
                "temperature": 0.0,  # No creativity, just formatting
                "num_predict": 350,  # Slightly more than writer for formatting
            },
        )
        return response["response"].strip()
    except Exception:
        # On error, return original — finalizer is non-critical
        return explanation
