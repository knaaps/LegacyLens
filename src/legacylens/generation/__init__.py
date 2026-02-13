"""Generation Module — Legacy single-shot explanation generator.

NOTE: This module is superseded by the agents/ module (Phase 2).
The Writer→Critic loop in agents/ provides verified explanations.
This file is kept for reference and backward compatibility.

Usage (legacy):
    from legacylens.generation import generate_explanation
    explanation = generate_explanation(code, query, metadata)
"""

from legacylens.generation.generator import generate_explanation

__all__ = ["generate_explanation"]
