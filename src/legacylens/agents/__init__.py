"""LegacyLens Agents - Multi-agent verification loop."""

from legacylens.agents.writer import write_explanation
from legacylens.agents.critic import critique_explanation, CritiqueResult
from legacylens.agents.orchestrator import generate_verified_explanation, VerifiedExplanation

__all__ = [
    "write_explanation",
    "critique_explanation",
    "CritiqueResult",
    "generate_verified_explanation",
    "VerifiedExplanation",
]
