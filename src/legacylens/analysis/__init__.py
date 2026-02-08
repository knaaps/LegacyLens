"""LegacyLens Analysis - Call graph and context slicing."""

from legacylens.analysis.call_graph import CallGraph
from legacylens.analysis.context_slicer import slice_context, SlicedContext

__all__ = [
    "CallGraph",
    "slice_context",
    "SlicedContext",
]
