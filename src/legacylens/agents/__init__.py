"""LegacyLens Agents — Multi-agent verification loop."""

from legacylens.agents.provider import llm_generate
from legacylens.agents.writer import write_explanation
from legacylens.agents.critic import critique_explanation, CritiqueResult
from legacylens.agents.orchestrator import generate_verified_explanation, VerifiedExplanation

__all__ = [
    "llm_generate",
    "write_explanation",
    "critique_explanation",
    "CritiqueResult",
    "generate_verified_explanation",
    "VerifiedExplanation",
]
