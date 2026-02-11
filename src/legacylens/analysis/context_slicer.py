"""Context Slicer - Extract deterministic context for a function.

Uses the call graph to get 1-hop callers and callees, providing
structured context for explanation generation.
"""

from dataclasses import dataclass, field

from legacylens.analysis.call_graph import CallGraph, FunctionNode


@dataclass
class SlicedContext:
    """
    Deterministically sliced context for a target function.
    
    Contains the target code plus related functions (callers/callees).
    """
    
    target: FunctionNode
    callers: list[FunctionNode] = field(default_factory=list)
    callees: list[FunctionNode] = field(default_factory=list)
    
    @property
    def has_context(self) -> bool:
        """True if we have any related functions."""
        return bool(self.callers or self.callees)
    
    def to_context_dict(self) -> dict:
        """
        Convert to context dict for the Writer agent.
        
        Returns:
            Dict with static_facts, callers, callees for prompting
        """
        return {
            "code": self.target.code,
            "static_facts": {
                "name": self.target.qualified_name,
                "file_path": self.target.file_path,
                "calls": self.target.calls,
            },
            "callers": [c.code for c in self.callers[:2]],  # Limit to 2
            "callees": [c.code for c in self.callees[:2]],  # Limit to 2
        }
    
    @property
    def total_lines(self) -> int:
        """Approximate total lines of context."""
        lines = self.target.code.count("\n") + 1
        for node in self.callers + self.callees:
            lines += node.code.count("\n") + 1
        return lines


def slice_context(
    target_name: str,
    graph: CallGraph,
    max_callers: int = 2,
    max_callees: int = 2,
) -> SlicedContext | None:
    """
    Extract 1-hop context for a function from the call graph.
    
    Args:
        target_name: Name of the function to get context for
        graph: The CallGraph containing function relationships
        max_callers: Maximum number of caller functions to include
        max_callees: Maximum number of callee functions to include
        
    Returns:
        SlicedContext if target found, None otherwise
    """
    target = graph.get_node(target_name)
    if not target:
        return None
    
    # Get 1-hop callers (functions that call target)
    callers = graph.get_caller_nodes(target_name)[:max_callers]
    
    # Get 1-hop callees (functions that target calls)
    callees = graph.get_callee_nodes(target_name)[:max_callees]
    
    return SlicedContext(
        target=target,
        callers=callers,
        callees=callees,
    )


def build_hybrid_context(
    query: str,
    graph: CallGraph,
    rag_results: list[dict],
) -> dict:
    """
    Build hybrid context: try deterministic slicing first, fallback to RAG.
    
    Args:
        query: The user's query (often a function name)
        graph: The CallGraph
        rag_results: Results from vector search as fallback
        
    Returns:
        Context dict for the Writer agent
    """
    # Try deterministic slicing first
    sliced = slice_context(query, graph)
    
    if sliced and sliced.has_context:
        # We have graph context - use it
        context = sliced.to_context_dict()
        context["source"] = "deterministic"
        return context
    
    # Fallback to RAG results
    if rag_results:
        result = rag_results[0]
        meta = result.get("metadata", {})
        context = {
            "code": result.get("code", ""),
            "static_facts": {
                "name": meta.get("qualified_name", query),
                "file_path": meta.get("file_path", ""),
                "complexity": meta.get("complexity", 0),
                "line_count": meta.get("line_count", 0),
                "calls": meta.get("calls", "").split(",") if meta.get("calls") else [],
            },
            "callers": [],
            "callees": [],
            "source": "rag",
        }
        return context
    
    # No context available
    return {
        "code": "",
        "static_facts": {},
        "callers": [],
        "callees": [],
        "source": "none",
    }
