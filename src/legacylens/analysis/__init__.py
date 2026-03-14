"""LegacyLens Analysis — Call graph, context slicing, code health scoring, and regeneration validation."""

from legacylens.analysis.call_graph import CallGraph
from legacylens.analysis.codebalance import CodeBalanceScore, score_code
from legacylens.analysis.context_slicer import SlicedContext, slice_context
from legacylens.analysis.regeneration_validator import compute_ast_similarity, validate_regeneration

__all__ = [
    "CallGraph",
    "slice_context",
    "SlicedContext",
    "score_code",
    "CodeBalanceScore",
    "validate_regeneration",
    "compute_ast_similarity",
]
