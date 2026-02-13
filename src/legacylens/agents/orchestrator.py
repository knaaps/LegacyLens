"""Orchestrator - Runs the Writer→Critic verification loop.

The orchestrator coordinates the multi-agent verification:
1. Writer drafts an explanation
2. Critic checks for hallucinations
3. If failed, Writer revises with feedback
4. Repeat until passed or max iterations
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
    writer_model: str = "deepseek-coder:6.7b",
    critic_model: str = "qwen2.5-coder:7b",
) -> VerifiedExplanation:
    """
    Run the Writer→Critic verification loop.

    Args:
        code: Source code to explain
        context: Context dict (static_facts, callers, callees, etc.)
        max_iterations: Maximum revision attempts
        writer_model: Model for Writer agent
        critic_model: Model for Critic agent

    Returns:
        VerifiedExplanation with final result and metadata
    """
    explanation = ""
    critique = None
    iteration = 0

    revision_context = context.copy()

    for iteration in range(1, max_iterations + 1):
        # Step 1: Writer generates/revises explanation
        explanation = write_explanation(
            code=code,
            context=revision_context,
            model=writer_model,
        )

        # Check for writer errors
        if explanation.startswith("[Writer Error:"):
            return VerifiedExplanation(
                explanation=explanation,
                verified=False,
                confidence=0,
                iterations=iteration,
                critique=None,
            )

        # Step 2: Critic verifies
        critique = critique_explanation(
            code=code,
            explanation=explanation,
            model=critic_model,
        )

        # If passed, we're done
        if critique.passed:
            return VerifiedExplanation(
                explanation=explanation,
                verified=True,
                confidence=critique.confidence,
                iterations=iteration,
                critique=critique,
            )

        # If failed, add feedback for next iteration
        if critique.issues:
            revision_context["revision_feedback"] = (
                f"Previous explanation had issues: {', '.join(critique.issues)}. "
                f"Suggestions: {critique.suggestions}"
            )

    # Max iterations reached without passing
    return VerifiedExplanation(
        explanation=explanation,
        verified=False,
        confidence=critique.confidence if critique else 0,
        iterations=iteration,
        critique=critique,
    )
