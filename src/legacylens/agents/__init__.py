"""LegacyLens Agents — Multi-agent verification loop."""

from legacylens.agents.critic import CritiqueResult, clear_critique_cache, critique_explanation
from legacylens.agents.finalizer import finalize_explanation
from legacylens.agents.orchestrator import VerifiedExplanation, generate_verified_explanation
from legacylens.agents.provider import llm_generate
from legacylens.agents.utils import (
    build_pitfall_guidance,
    load_known_pitfalls,
    record_critique_pitfalls,
    with_prompt_repetition,
)
from legacylens.agents.writer import write_explanation

__all__ = [
    "llm_generate",
    "with_prompt_repetition",
    "build_pitfall_guidance",
    "load_known_pitfalls",
    "record_critique_pitfalls",
    "write_explanation",
    "critique_explanation",
    "CritiqueResult",
    "clear_critique_cache",
    "finalize_explanation",
    "generate_verified_explanation",
    "VerifiedExplanation",
]
