"""Base parser interface and data models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FunctionMetadata:
    """Metadata extracted from a function/method."""
    
    name: str
    file_path: str
    start_line: int
    end_line: int
    code: str
    language: str
    
    # Static analysis metrics
    complexity: int = 1  # McCabe cyclomatic complexity
    line_count: int = 0
    
    # Dependencies
    calls: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    
    # Optional: class context
    class_name: Optional[str] = None
    
    # ── Structural hints (populated by parser, consumed by CodeBalance/Critic) ──
    has_try_catch: bool = False
    has_loops: bool = False
    return_count: int = 0         # Number of return statements
    param_count: int = 0
    field_reads: list[str] = field(default_factory=list)   # e.g. this.name
    field_writes: list[str] = field(default_factory=list)  # e.g. this.name = ...
    
    @property
    def qualified_name(self) -> str:
        """Return fully qualified name (ClassName.methodName or just functionName)."""
        if self.class_name:
            return f"{self.class_name}.{self.name}"
        return self.name
    
    def to_dict(self) -> dict:
        """Convert to dictionary for ChromaDB metadata."""
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "complexity": self.complexity,
            "line_count": self.line_count,
            "calls": ",".join(self.calls),  # ChromaDB needs simple types
            "imports": ",".join(self.imports),
            "class_name": self.class_name or "",
            "has_try_catch": self.has_try_catch,
            "has_loops": self.has_loops,
            "return_count": self.return_count,
            "param_count": self.param_count,
            "field_reads": ",".join(self.field_reads),
            "field_writes": ",".join(self.field_writes),
        }


class CodeParser(ABC):
    """Abstract base class for language-specific parsers."""
    
    @property
    @abstractmethod
    def language(self) -> str:
        """Return the language this parser handles (e.g., 'java', 'python')."""
        pass
    
    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """Return file extensions this parser handles (e.g., ['.java'])."""
        pass
    
    @abstractmethod
    def parse_file(self, file_path: Path) -> list[FunctionMetadata]:
        """
        Parse a source file and extract all functions/methods.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            List of FunctionMetadata for each function/method found
        """
        pass
    
    @abstractmethod
    def calculate_complexity(self, code: str) -> int:
        """
        Calculate McCabe cyclomatic complexity for a code block.
        
        Args:
            code: The source code string
            
        Returns:
            Cyclomatic complexity score (1 = simplest)
        """
        pass
    
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file."""
        return file_path.suffix.lower() in self.file_extensions
