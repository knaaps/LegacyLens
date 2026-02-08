"""Call Graph - Simple in-memory graph of function calls.

Builds a bidirectional graph from the 'calls' data extracted by parsers.
Supports querying callers (who calls X?) and callees (what does X call?).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FunctionNode:
    """A function in the call graph."""
    
    name: str
    qualified_name: str
    file_path: str
    code: str
    calls: list[str] = field(default_factory=list)


class CallGraph:
    """
    In-memory call graph for deterministic context assembly.
    
    The graph tracks:
    - callees: For function A, what functions does A call?
    - callers: For function B, what functions call B?
    
    Usage:
        graph = CallGraph()
        graph.add_function("processForm", calls=["validate", "save"])
        graph.add_function("validate", calls=[])
        
        graph.get_callees("processForm")  # ["validate", "save"]
        graph.get_callers("validate")      # ["processForm"]
    """
    
    def __init__(self):
        # name -> FunctionNode
        self._nodes: dict[str, FunctionNode] = {}
        
        # name -> list of names that call it
        self._callers: dict[str, list[str]] = defaultdict(list)
        
        # name -> list of names it calls (direct from node.calls)
        self._callees: dict[str, list[str]] = defaultdict(list)
    
    def add_function(
        self,
        name: str,
        qualified_name: str,
        file_path: str,
        code: str,
        calls: list[str],
    ) -> None:
        """
        Add a function to the graph.
        
        Args:
            name: Simple function name (e.g., "validate")
            qualified_name: Full name (e.g., "UserController.validate")
            file_path: Source file path
            code: Source code of the function
            calls: List of function names this function calls
        """
        node = FunctionNode(
            name=name,
            qualified_name=qualified_name,
            file_path=file_path,
            code=code,
            calls=calls,
        )
        
        self._nodes[name] = node
        self._callees[name] = calls
        
        # Update reverse mapping (callers)
        for callee in calls:
            if name not in self._callers[callee]:
                self._callers[callee].append(name)
    
    def get_node(self, name: str) -> Optional[FunctionNode]:
        """Get a function node by name."""
        return self._nodes.get(name)
    
    def get_callers(self, name: str) -> list[str]:
        """Get all functions that call the given function."""
        return self._callers.get(name, [])
    
    def get_callees(self, name: str) -> list[str]:
        """Get all functions that the given function calls."""
        return self._callees.get(name, [])
    
    def get_caller_nodes(self, name: str) -> list[FunctionNode]:
        """Get FunctionNode objects for all callers."""
        return [
            self._nodes[caller]
            for caller in self.get_callers(name)
            if caller in self._nodes
        ]
    
    def get_callee_nodes(self, name: str) -> list[FunctionNode]:
        """Get FunctionNode objects for all callees."""
        return [
            self._nodes[callee]
            for callee in self.get_callees(name)
            if callee in self._nodes
        ]
    
    def has_function(self, name: str) -> bool:
        """Check if a function exists in the graph."""
        return name in self._nodes
    
    @property
    def size(self) -> int:
        """Number of functions in the graph."""
        return len(self._nodes)
    
    def __contains__(self, name: str) -> bool:
        return self.has_function(name)
    
    def __len__(self) -> int:
        return self.size
