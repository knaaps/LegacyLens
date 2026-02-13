"""Legacy Explanation Generator — Single-shot LLM explanation.

NOTE: This is the Phase 1 generator. For Phase 2+, use the
agents/ module which provides Writer→Critic verified explanations.

This module sends code + static facts to an Ollama model and
returns a plain text explanation. No verification is performed.
"""

import ollama


def generate_explanation(
    code: str,
    query: str,
    metadata: dict,
    model: str = "deepseek-coder:6.7b",
) -> str:
    """
    Generate a single-shot explanation of code using Ollama.

    This is the legacy Phase 1 function. For verified explanations,
    use agents.orchestrator.generate_verified_explanation() instead.

    Args:
        code: Source code to explain
        query: The user's question about the code
        metadata: Static analysis facts (complexity, calls, etc.)
        model: Ollama model name (default: deepseek-coder:6.7b)

    Returns:
        Plain text explanation (unverified)
    """
    # Build static facts into the prompt
    facts = []
    if metadata.get("complexity"):
        facts.append(f"McCabe Complexity: {metadata['complexity']}")
    if metadata.get("line_count"):
        facts.append(f"Lines of code: {metadata['line_count']}")
    if metadata.get("calls"):
        calls = metadata["calls"]
        if isinstance(calls, str):
            calls = [c.strip() for c in calls.split(",") if c.strip()]
        if calls:
            facts.append(f"Function calls: {', '.join(calls[:5])}")

    facts_text = "\n".join(f"  • {f}" for f in facts) if facts else "  None available"

    prompt = f"""You are an expert developer explaining legacy code to a colleague.

CODE:
```
{code}
```

STATIC ANALYSIS FACTS:
{facts_text}

QUESTION: {query}

Provide a clear, structured explanation. Reference the static analysis
facts where relevant. Keep it concise but thorough."""

    try:
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={"temperature": 0.3},
        )
        return response["response"].strip()
    except Exception as e:
        return f"[Generation Error: {e}]"
