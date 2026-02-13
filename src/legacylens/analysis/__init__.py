"""LegacyLens Analysis - Call graph, context slicing, and code health scoring."""

from legacylens.analysis.call_graph import CallGraph
from legacylens.analysis.context_slicer import slice_context, SlicedContext
from legacylens.analysis.codebalance import score_code, CodeBalanceScore

__all__ = [
    "CallGraph",
    "slice_context",
    "SlicedContext",
    "score_code",
    "CodeBalanceScore",
]
