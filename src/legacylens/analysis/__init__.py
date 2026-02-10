"""LegacyLens Analysis - Static analysis and context assembly."""

from legacylens.analysis.call_graph import CallGraph, FunctionNode
from legacylens.analysis.context_slicer import (
    SlicedContext,
    slice_context,
    build_hybrid_context,
)
from legacylens.analysis.complexity import calculate_mccabe_complexity, complexity_label

__all__ = [
    "CallGraph",
    "FunctionNode",
    "SlicedContext",
    "slice_context",
    "build_hybrid_context",
    "calculate_mccabe_complexity",
    "complexity_label",
]
