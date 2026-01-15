"""Python parser using tree-sitter and radon for complexity."""

import re
from pathlib import Path
from typing import Optional

import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node

from .base import CodeParser, FunctionMetadata

# Try to import radon for more accurate complexity
try:
    from radon.complexity import cc_visit
    HAS_RADON = True
except ImportError:
    HAS_RADON = False


class PythonParser(CodeParser):
    """Parse Python source files using tree-sitter."""
    
    def __init__(self):
        self._parser = Parser(Language(tspython.language()))
    
    @property
    def language(self) -> str:
        return "python"
    
    @property
    def file_extensions(self) -> list[str]:
        return [".py"]
    
    def parse_file(self, file_path: Path) -> list[FunctionMetadata]:
        """Parse a Python file and extract all function/method definitions."""
        try:
            with open(file_path, "rb") as f:
                source_code = f.read()
        except (IOError, OSError) as e:
            print(f"Error reading {file_path}: {e}")
            return []
        
        tree = self._parser.parse(source_code)
        source_text = source_code.decode("utf-8")
        
        # Extract imports
        imports = self._extract_imports(tree.root_node, source_text)
        
        functions = []
        self._walk_tree(tree.root_node, source_text, file_path, imports, functions)
        return functions
    
    def _walk_tree(
        self,
        node: Node,
        source_text: str,
        file_path: Path,
        imports: list[str],
        functions: list[FunctionMetadata],
        current_class: Optional[str] = None,
    ) -> None:
        """Recursively walk AST to find function definitions."""
        
        # Track current class context
        if node.type == "class_definition":
            class_name_node = node.child_by_field_name("name")
            if class_name_node:
                current_class = class_name_node.text.decode("utf-8")
        
        # Found a function
        if node.type == "function_definition":
            metadata = self._extract_function_metadata(
                node, source_text, file_path, imports, current_class
            )
            if metadata:
                functions.append(metadata)
        
        # Recurse into children
        for child in node.children:
            self._walk_tree(child, source_text, file_path, imports, functions, current_class)
    
    def _extract_function_metadata(
        self,
        node: Node,
        source_text: str,
        file_path: Path,
        imports: list[str],
        class_name: Optional[str],
    ) -> Optional[FunctionMetadata]:
        """Extract metadata from a function node."""
        
        # Get function name
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        
        func_name = name_node.text.decode("utf-8")
        
        # Skip private/dunder methods optionally (we'll include them for completeness)
        
        # Extract code
        start_byte = node.start_byte
        end_byte = node.end_byte
        code = source_text[start_byte:end_byte]
        
        # Line numbers (1-indexed)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        
        # Extract function calls
        calls = self._extract_calls(node, source_text)
        
        # Calculate complexity
        complexity = self.calculate_complexity(code)
        
        return FunctionMetadata(
            name=func_name,
            file_path=str(file_path),
            start_line=start_line,
            end_line=end_line,
            code=code,
            language=self.language,
            complexity=complexity,
            line_count=end_line - start_line + 1,
            calls=calls,
            imports=imports,
            class_name=class_name,
        )
    
    def _extract_imports(self, root: Node, source_text: str) -> list[str]:
        """Extract all import statements from the file."""
        imports = []
        
        def find_imports(node: Node):
            if node.type in ("import_statement", "import_from_statement"):
                import_text = source_text[node.start_byte:node.end_byte]
                imports.append(import_text.strip())
            
            for child in node.children:
                find_imports(child)
        
        find_imports(root)
        return imports
    
    def _extract_calls(self, node: Node, source_text: str) -> list[str]:
        """Extract function calls from a function body."""
        calls = []
        
        def find_calls(n: Node):
            if n.type == "call":
                # Get the function being called
                func_node = n.child_by_field_name("function")
                if func_node:
                    # Handle simple calls and attribute calls (obj.method)
                    if func_node.type == "identifier":
                        call_name = func_node.text.decode("utf-8")
                    elif func_node.type == "attribute":
                        attr_node = func_node.child_by_field_name("attribute")
                        if attr_node:
                            call_name = attr_node.text.decode("utf-8")
                        else:
                            call_name = source_text[func_node.start_byte:func_node.end_byte]
                    else:
                        call_name = source_text[func_node.start_byte:func_node.end_byte]
                    
                    if call_name not in calls:
                        calls.append(call_name)
            
            for child in n.children:
                find_calls(child)
        
        find_calls(node)
        return calls
    
    def calculate_complexity(self, code: str) -> int:
        """
        Calculate McCabe cyclomatic complexity for Python code.
        
        Uses radon if available, otherwise falls back to regex counting.
        """
        if HAS_RADON:
            try:
                # Radon returns a list of complexity results
                results = cc_visit(code)
                if results:
                    # Return complexity of the first (presumably only) function
                    return results[0].complexity
            except Exception:
                pass  # Fall back to regex method
        
        # Fallback: count decision points
        complexity = 1  # Base complexity
        
        patterns = [
            r'\bif\b',
            r'\belif\b',
            r'\bfor\b',
            r'\bwhile\b',
            r'\bexcept\b',
            r'\band\b',
            r'\bor\b',
            r'\bif\s+\w+\s+else\b',  # Ternary
        ]
        
        for pattern in patterns:
            complexity += len(re.findall(pattern, code))
        
        return complexity
