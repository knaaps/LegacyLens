"""LegacyLens Analysis — Call graph, context slicing, code health scoring, and regeneration validation."""

from legacylens.analysis.call_graph import CallGraph
from legacylens.analysis.context_slicer import slice_context, SlicedContext
from legacylens.analysis.codebalance import score_code, CodeBalanceScore
from legacylens.analysis.regeneration_validator import validate_regeneration, compute_ast_similarity

__all__ = [
    "CallGraph",
    "slice_context",
    "SlicedContext",
    "score_code",
    "CodeBalanceScore",
    "validate_regeneration",
    "compute_ast_similarity",
]
