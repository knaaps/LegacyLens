"""Prompt Repetition Wrapper — Adapted from Leviathan et al. (2025).

Theory:
    Repeating the prompt enables full token attention in causal LLMs,
    boosting factual recall and pattern matching without extra generation
    tokens or latency.  The paper reports 47/70 wins (McNemar p<0.1) on
    non-reasoning tasks — directly applicable to code regeneration where
    the model must faithfully reproduce structural elements.

Variants:
    simple  — Duplicate the prompt once (baseline attention boost)
    verbose — Duplicate with bridging text ("Let me repeat that for clarity")
    x3      — Triple repeat for complex AST recall (e.g., deep nesting)

Code-Gen Mode:
    When for_code_gen=True, each copy is appended with an instruction to
    output code directly, leveraging Opus 4.6-style self-coding without
    chain-of-thought overhead.

References:
    Leviathan et al. (2025) — Prompt Repetition in LLMs
    VAPU verification loops — compositional fidelity checks
    C2AADL — structural fidelity in code regeneration
"""


def with_prompt_repetition(
    system_prompt: str,
    user_query: str,
    variant: str = "simple",
    for_code_gen: bool = False,
) -> str:
    """
    Apply prompt repetition to boost factual/structural fidelity.

    Args:
        system_prompt: The system-level instruction (e.g., "You are a code
                       regeneration expert.")
        user_query:    The user-level content (e.g., explanation + regen
                       instructions)
        variant:       Repetition strategy — "simple", "verbose", or "x3"
        for_code_gen:  If True, append a direct-output instruction to suppress
                       explanatory text and reasoning traces

    Returns:
        The combined, repeated prompt string ready for LLM consumption.

    Theory:
        Enables full prompt token attention, improving factual/code fidelity
        without latency hit.  47/70 wins in non-reasoning tasks (Leviathan
        et al. 2025).  For code-gen (e.g., regeneration), boosts structural
        match — target: +5–15% fidelity.  Variants: simple for baseline;
        verbose/x3 for complex AST recall.
    """
    full_prompt = f"{system_prompt}\n\n{user_query}"

    if for_code_gen:
        full_prompt += (
            "\nOutput the regenerated code directly, "
            "no explanations or reasoning."
        )

    if variant == "simple":
        return full_prompt + "\n\n" + full_prompt

    if variant == "verbose":
        return (
            full_prompt
            + "\n\nLet me repeat that for clarity:\n"
            + full_prompt
        )

    if variant == "x3":
        return (
            full_prompt
            + "\n\nLet me repeat that:\n"
            + full_prompt
            + "\n\nOne more time to ensure accuracy:\n"
            + full_prompt
        )

    # Fallback — no repetition (unknown variant)
    return full_prompt


# ---------------------------------------------------------------------------
# Meta-Prompt Accumulation — lightweight MAML-style pitfall tracking
# Inspired by Kawabe & Takano (2026): shared refinements across agents
# ---------------------------------------------------------------------------

import json
from pathlib import Path
from collections import Counter

_DEFAULT_PITFALLS_PATH = Path("results/known_pitfalls.json")


def load_known_pitfalls(path: Path | None = None) -> dict:
    """Load accumulated failure patterns from disk."""
    p = path or _DEFAULT_PITFALLS_PATH
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"hallucination": [], "completeness": [], "safety": []}


def save_known_pitfalls(data: dict, path: Path | None = None) -> None:
    """Persist accumulated pitfalls to disk."""
    p = path or _DEFAULT_PITFALLS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


def record_critique_pitfalls(critique, threshold: int = 2, path: Path | None = None) -> dict:
    """Record failure patterns from a CritiqueResult and prune by frequency.

    Only patterns seen >= threshold times are kept, preventing one-off
    noise from polluting the meta-prompt.
    """
    pitfalls = load_known_pitfalls(path)

    for issue in critique.issues:
        lower = issue.lower()
        if "not found in code" in lower or "hallucin" in lower:
            pitfalls["hallucination"].append(issue)
        elif "missing coverage" in lower or "missing" in lower:
            pitfalls["completeness"].append(issue)
        elif "risk" in lower or "safety" in lower:
            pitfalls["safety"].append(issue)

    # De-duplicate and keep only recurring patterns
    for cat in pitfalls:
        cnt = Counter(pitfalls[cat])
        pitfalls[cat] = [item for item, c in cnt.most_common(5) if c >= threshold]

    save_known_pitfalls(pitfalls, path)
    return pitfalls


def build_pitfall_guidance(path: Path | None = None) -> str:
    """Build a short instruction string from accumulated pitfalls.

    This is prepended to the Writer's prompt so it avoids repeating
    known mistakes — a lightweight meta-learning signal.
    """
    pitfalls = load_known_pitfalls(path)
    parts = []

    if pitfalls.get("hallucination"):
        parts.append(
            "AVOID these known hallucination patterns: "
            + "; ".join(pitfalls["hallucination"][:3])
        )
    if pitfalls.get("completeness"):
        parts.append(
            "Ensure coverage of these frequently missed aspects: "
            + "; ".join(pitfalls["completeness"][:3])
        )
    if pitfalls.get("safety"):
        parts.append(
            "Always mention these safety concerns when present: "
            + "; ".join(pitfalls["safety"][:3])
        )

    return "\n".join(parts)
