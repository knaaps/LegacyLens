"""Parser Module — Reads source code and extracts function metadata.

Supported languages:
    - Java  (via tree-sitter)
    - Python (via tree-sitter + optional radon)

Each parser extracts:
    - Function/method names and code
    - Line numbers and file path
    - McCabe cyclomatic complexity
    - Function calls (for the call graph)
    - Import statements

Usage:
    from legacylens.parser import JavaParser, PythonParser

    parser = JavaParser()
    functions = parser.parse_file(Path("MyClass.java"))
"""

from legacylens.parser.base import CodeParser, FunctionMetadata
from legacylens.parser.java_parser import JavaParser
from legacylens.parser.python_parser import PythonParser

__all__ = [
    "CodeParser",
    "FunctionMetadata",
    "JavaParser",
    "PythonParser",
]
