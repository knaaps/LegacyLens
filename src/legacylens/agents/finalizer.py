"""Finalizer Agent — Polishes and structures explanation output.

The Finalizer is the third agent in the pipeline:
    Writer (drafts) → Critic (verifies) → Finalizer (polishes)

Its role is purely editorial: take a verified explanation and make it
cleaner, more structured, and easier for a developer to read.

Key design decisions:
    - Only runs when Critic returns PASS (verified explanations only)
    - Uses a higher temperature (0.5) for fluency/readability
    - Never adds factual claims — only restructures existing ones
    - If the explanation is already short/clean, returns it unchanged
    - Fails gracefully: returns original if LLM call fails
"""

from legacylens.agents.provider import llm_generate

# Minimum explanation length worth polishing (very short = no-op)
_MIN_LENGTH_FOR_POLISH = 200


def finalize_explanation(
    explanation: str,
    code: str,
    model: str = "deepseek-coder:6.7b",
) -> str:
    """
    Polish a verified explanation for readability.

    Takes a Writer-produced, Critic-verified explanation and restructures
    it for clarity. Does NOT add new facts — only edits existing content.

    Args:
        explanation: The verified explanation from the Writer
        code: Original source code (for context grounding)
        model: Model name (auto-mapped for Groq if LLM_PROVIDER=groq)

    Returns:
        Polished explanation text (or original if polish fails / not needed)
    """
    # Skip very short explanations — they're already concise
    if len(explanation) < _MIN_LENGTH_FOR_POLISH:
        return explanation

    prompt = f"""You are a technical writing editor. Your job is to polish and structure
developer explanations — NOT to add new facts, only to improve clarity.

ORIGINAL CODE (for reference only — do not add new claims):
```
{code[:1500]}
```

EXPLANATION TO POLISH:
{explanation}

EDITING RULES:
1. Improve sentence clarity and flow
2. Add structure (short paragraphs for: purpose, parameters, return, side effects)
3. Remove redundancy and awkward phrasing
4. DO NOT add any facts not present in the original explanation
5. DO NOT change technical terms, method names, or described behaviours
6. Keep it the same length or shorter

POLISHED EXPLANATION:"""

    try:
        polished = llm_generate(prompt=prompt, model=model, temperature=0.5)
        # Safety guard: if output is empty or error-like, return original
        if not polished or polished.startswith("[") or len(polished) < 50:
            return explanation
        return polished
    except Exception:
        # Fail gracefully — never break the pipeline
        return explanation
