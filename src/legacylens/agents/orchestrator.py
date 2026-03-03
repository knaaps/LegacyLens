"""Orchestrator — Runs the Writer→Critic→Finalizer verification pipeline.

The orchestrator coordinates the multi-agent verification:
1. Writer drafts an explanation (temperature=0.3)
2. Critic checks for hallucinations (returns PASS / FAIL / REVISE)
3. If REVISE, Writer revises with structured feedback
4. Repeat until PASS, FAIL, or max iterations (5)
5. (Optional) Finalizer polishes the verified explanation
6. (Optional) Validate via code regeneration
"""

from dataclasses import dataclass, field
from typing import Optional

from legacylens.agents.writer import write_explanation
from legacylens.agents.critic import critique_explanation, CritiqueResult
from legacylens.agents.finalizer import finalize_explanation


@dataclass
class VerifiedExplanation:
    """Final output of the verification loop."""

    explanation: str
    verified: bool
    confidence: int  # 0-100
    iterations: int
    critique: Optional[CritiqueResult] = None
    fidelity_score: Optional[float] = None  # 0.0-1.0, from regeneration validation
    fidelity_details: str = ""

    @property
    def status_string(self) -> str:
        status = "✓ Verified" if self.verified else "⚠ Unverified"
        parts = [f"{status} (Confidence: {self.confidence}%)"]
        if self.fidelity_score is not None:
            parts.append(f"Fidelity: {self.fidelity_score:.0%}")
        return " | ".join(parts)

    @property
    def verdict(self) -> str:
        """The Critic's final verdict (PASS/FAIL/REVISE)."""
        return self.critique.verdict if self.critique else "UNKNOWN"

    @property
    def critique_json(self) -> dict | None:
        """The Critic's full JSON output for logging/reports."""
        return self.critique.to_json() if self.critique else None


def generate_verified_explanation(
    code: str,
    context: dict,
    max_iterations: int = 5,
    writer_model: str = "deepseek-coder:6.7b",
    critic_model: str = "qwen2.5-coder:7b",
    run_regeneration: bool = True,
    run_finalizer: bool = False,
    language: str = "java",
    repetition_variant: str | None = None,
) -> VerifiedExplanation:
    """
    Run the Writer→Critic→Finalizer verification pipeline.

    The loop uses three-state verdict logic:
    - PASS:   Accept immediately, optionally polish with Finalizer
    - REVISE: Writer gets structured feedback, tries again (up to max_iterations)
    - FAIL:   Hard stop, explanation has fundamental problems

    Early accept: If factual ≥ 90% and completeness ≥ 95%, accept on first pass.

    Args:
        code: Source code to explain
        context: Context dict (static_facts, callers, callees, etc.)
        max_iterations: Maximum revision attempts (default 5)
        writer_model: Model for Writer and Finalizer agents
        critic_model: Model for Critic agent
        run_regeneration: If True, validate explanation via code regeneration
        run_finalizer: If True, run the Finalizer on verified explanations
        language: Source code language ("java" or "python")
        repetition_variant: Prompt repetition strategy for Critic verification
            and regeneration (None, "simple", "verbose", or "x3").

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

        # Step 2: Critic verifies (returns PASS / FAIL / REVISE)
        critique = critique_explanation(
            code=code,
            explanation=explanation,
            model=critic_model,
            repetition_variant=repetition_variant,
        )

        # PASS → accept immediately
        if critique.verdict == "PASS":
            break

        # FAIL → hard stop, don't bother revising
        if critique.verdict == "FAIL":
            break

        # REVISE → feed categorized issues back, let the Writer try again
        if critique.issues:
            revision_context["revision_feedback"] = critique.to_revision_prompt()

            # Record failure patterns for meta-prompt accumulation
            try:
                from legacylens.agents.utils import record_critique_pitfalls
                record_critique_pitfalls(critique)
            except Exception:
                pass  # Non-critical — don't break the loop

    # --- Optional: Regeneration validation ---
    fidelity_score = None
    fidelity_details = ""

    if run_regeneration and explanation and not explanation.startswith("[Writer Error:"):
        try:
            from legacylens.analysis.regeneration_validator import validate_regeneration

            regen_result = validate_regeneration(
                original_code=code,
                explanation=explanation,
                language=language,
                model=writer_model,
                repetition_variant=repetition_variant,
            )
            fidelity_score = regen_result["fidelity"]
            fidelity_details = regen_result["details"]
        except Exception as e:
            fidelity_details = f"Regeneration error: {e}"

    is_verified = critique.passed if critique else False

    # --- Optional: Finalizer (readability polish) ---
    if run_finalizer and is_verified and explanation:
        try:
            explanation = finalize_explanation(
                explanation=explanation,
                code=code,
                model=writer_model,
            )
        except Exception:
            pass  # Non-critical — don't break the pipeline

    return VerifiedExplanation(
        explanation=explanation,
        verified=is_verified,
        confidence=critique.confidence if critique else 0,
        iterations=iteration,
        critique=critique,
        fidelity_score=fidelity_score,
        fidelity_details=fidelity_details,
    )
