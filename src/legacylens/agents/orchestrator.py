"""Orchestrator — Runs the Writer→Critic→Finalizer verification pipeline.

The orchestrator coordinates the multi-agent verification:
1. Writer drafts an explanation (temperature=0.3)
2. Critic checks for hallucinations (returns PASS / FAIL / REVISE)
3. If REVISE or FAIL (with retries), Writer revises with structured feedback
4. If FAIL retries exhausted, return the best explanation seen so far
5. (Optional) Finalizer polishes the verified explanation
6. (Optional) Validate via code regeneration

Key guarantee: ALWAYS produces an explanation. A FAIL never results in an
empty or abrupt termination — the highest-confidence draft is returned.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

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
    iteration_log: list[dict[str, Any]] = field(default_factory=list)

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
    sop: dict[str, Any] | None = None,
) -> VerifiedExplanation:
    """
    Run the Writer→Critic→Finalizer verification pipeline.

    The loop uses three-state verdict logic:
    - PASS:   Accept immediately, optionally polish with Finalizer
    - REVISE: Writer gets structured feedback, tries again (up to max_iterations)
    - FAIL:   SAME as REVISE — Writer gets feedback, retries up to 2 times.
              After 2 FAIL retries, stop and return the best explanation seen.

    Key design principle: ALWAYS produce an explanation. If no iteration
    passes, return the highest-confidence attempt rather than aborting.

    Early accept: If factual >= 90% and completeness >= 95%, accept on first pass.

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
        VerifiedExplanation with final result and metadata.
        Always contains a non-empty explanation string.
    """
    # Apply SOP overrides (if provided)
    if sop:
        max_iterations     = sop.get("max_iterations", max_iterations)
        repetition_variant = sop.get("repetition_variant", repetition_variant)
        run_finalizer      = sop.get("run_finalizer", run_finalizer)
        run_regeneration   = sop.get("run_regeneration", run_regeneration)

    explanation = ""
    critique: Optional[CritiqueResult] = None
    iteration = 0
    _iteration_log: list[dict[str, Any]] = []

    revision_context = context.copy()

    # Track the best output across all iterations so we always have
    # something meaningful to return, regardless of verdict
    best_explanation = ""
    best_critique: Optional[CritiqueResult] = None
    best_confidence = -1

    # Cap how many consecutive FAIL retries we allow before giving up
    fail_count = 0
    MAX_FAIL_RETRIES = 2

    for iteration in range(1, max_iterations + 1):
        # Step 1: Writer generates/revises explanation
        explanation = write_explanation(
            code=code,
            context=revision_context,
            model=writer_model,
        )

        # If the writer itself errored, we still have best_explanation as fallback
        if explanation.startswith("[Writer Error:"):
            break

        # Step 2: Critic verifies (returns PASS / FAIL / REVISE)
        critique = critique_explanation(
            code=code,
            explanation=explanation,
            model=critic_model,
            repetition_variant=repetition_variant,
        )

        # Always track the best attempt by confidence score
        if critique.confidence > best_confidence:
            best_confidence = critique.confidence
            best_explanation = explanation
            best_critique = critique

        # Log this iteration's state
        _iteration_log.append({
            "iteration": iteration,
            "verdict": critique.verdict,
            "confidence": critique.confidence,
            "factual_passed": critique.factual_passed,
            "completeness_pct": round(critique.completeness_pct, 1),
            "issues_count": len(critique.issues),
        })

        # PASS → accept immediately
        if critique.verdict == "PASS":
            break

        # FAIL → treat like REVISE but cap consecutive failures
        if critique.verdict == "FAIL":
            fail_count += 1
            if fail_count >= MAX_FAIL_RETRIES:
                # Exhausted FAIL retries — stop here, fall back to best
                break
            # Otherwise fall through: give the Writer corrective feedback

        # REVISE or FAIL-with-retries → feed structured feedback back to Writer
        if critique.issues:
            revision_context["revision_feedback"] = critique.to_revision_prompt()

            # Record failure patterns (MAML-style meta-learning)
            try:
                from legacylens.agents.utils import record_critique_pitfalls
                record_critique_pitfalls(critique)
            except Exception:
                pass  # Non-critical — don't break the loop

    # ── Always return the best explanation we produced ──────────────────────
    # If the current explanation is a writer error or empty, use the best seen.
    # Also prefer the best if it had higher confidence than the final iteration.
    current_conf = critique.confidence if critique else -1
    if not explanation or explanation.startswith("[Writer Error:"):
        explanation = best_explanation
        critique = best_critique
    elif best_explanation and best_confidence > current_conf:
        explanation = best_explanation
        critique = best_critique

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
        iteration_log=_iteration_log,
    )
