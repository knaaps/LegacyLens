"""Orchestrator - Runs the Writer→Critic verification loop.

Optimized for runtime:
- Uses a single model for both Writer and Critic (no model switching)
- Default 1 iteration (verify once), max 2 on retry
- Short-circuits on writer errors
"""

from dataclasses import dataclass
from typing import Optional

from legacylens.agents.writer import write_explanation
from legacylens.agents.critic import critique_explanation, CritiqueResult


@dataclass
class VerifiedExplanation:
    """Final output of the verification loop."""

    explanation: str
    verified: bool
    confidence: int  # 0-100
    iterations: int
    critique: Optional[CritiqueResult] = None

    @property
    def status_string(self) -> str:
        if self.verified:
            return f"✓ Verified (Confidence: {self.confidence}%)"
        else:
            return f"⚠ Unverified (Confidence: {self.confidence}%)"


def generate_verified_explanation(
    code: str,
    context: dict,
    max_iterations: int = 2,
    model: str = "deepseek-coder:6.7b",
) -> VerifiedExplanation:
    """
    Run the Writer→Critic verification loop.

    Uses a SINGLE model for both agents to avoid the overhead of
    loading/switching between two separate models.

    Args:
        code: Source code to explain
        context: Context dict (static_facts, callers, callees, etc.)
        max_iterations: Maximum revision attempts (default 2)
        model: Single Ollama model used for both Writer and Critic

    Returns:
        VerifiedExplanation with final result and metadata
    """
    explanation = ""
    critique = None

    # Copy context so we can add revision feedback without mutating
    revision_context = context.copy()

    for iteration in range(1, max_iterations + 1):
        # Step 1: Writer generates/revises
        explanation = write_explanation(
            code=code,
            context=revision_context,
            model=model,
        )

        # Short-circuit on writer failure
        if explanation.startswith("[Writer Error:"):
            return VerifiedExplanation(
                explanation=explanation,
                verified=False,
                confidence=0,
                iterations=iteration,
            )

        # Step 2: Critic verifies (same model, different temp)
        critique = critique_explanation(
            code=code,
            explanation=explanation,
            model=model,
        )

        # Pass → done
        if critique.passed:
            return VerifiedExplanation(
                explanation=explanation,
                verified=True,
                confidence=critique.confidence,
                iterations=iteration,
                critique=critique,
            )

        # Fail → feed issues back for next iteration
        if critique.issues and iteration < max_iterations:
            revision_context["revision_feedback"] = ", ".join(critique.issues)

    # Max iterations exhausted
    return VerifiedExplanation(
        explanation=explanation,
        verified=False,
        confidence=critique.confidence if critique else 0,
        iterations=max_iterations,
        critique=critique,
    )
