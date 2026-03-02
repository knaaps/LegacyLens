"""LegacyLens Agents — Multi-agent verification loop."""

from legacylens.agents.provider import llm_generate
from legacylens.agents.utils import (
    with_prompt_repetition,
    build_pitfall_guidance,
    load_known_pitfalls,
    record_critique_pitfalls,
)
from legacylens.agents.writer import write_explanation
from legacylens.agents.critic import critique_explanation, CritiqueResult, clear_critique_cache
from legacylens.agents.orchestrator import generate_verified_explanation, VerifiedExplanation

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
    "generate_verified_explanation",
    "VerifiedExplanation",
]

