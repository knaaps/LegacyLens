"""Java parser using tree-sitter."""

import re
from pathlib import Path
from typing import Optional

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser, Node

from .base import CodeParser, FunctionMetadata


class JavaParser(CodeParser):
    """Parse Java source files using tree-sitter."""
    
    def __init__(self):
        self._parser = Parser(Language(tsjava.language()))
    
    @property
    def language(self) -> str:
        return "java"
    
    @property
    def file_extensions(self) -> list[str]:
        return [".java"]
    
    def parse_file(self, file_path: Path) -> list[FunctionMetadata]:
        """Parse a Java file and extract all method declarations."""
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
        
        methods = []
        self._walk_tree(tree.root_node, source_text, file_path, imports, methods)
        return methods
    
    def _walk_tree(
        self,
        node: Node,
        source_text: str,
        file_path: Path,
        imports: list[str],
        methods: list[FunctionMetadata],
        current_class: Optional[str] = None,
    ) -> None:
        """Recursively walk AST to find method declarations."""
        
        # Track current class context
        if node.type == "class_declaration":
            class_name_node = node.child_by_field_name("name")
            if class_name_node:
                current_class = class_name_node.text.decode("utf-8")
        
        # Found a method
        if node.type == "method_declaration":
            metadata = self._extract_method_metadata(
                node, source_text, file_path, imports, current_class
            )
            if metadata:
                methods.append(metadata)
        
        # Constructor
        if node.type == "constructor_declaration":
            metadata = self._extract_method_metadata(
                node, source_text, file_path, imports, current_class, is_constructor=True
            )
            if metadata:
                methods.append(metadata)
        
        # Recurse into children
        for child in node.children:
            self._walk_tree(child, source_text, file_path, imports, methods, current_class)
    
    def _extract_method_metadata(
        self,
        node: Node,
        source_text: str,
        file_path: Path,
        imports: list[str],
        class_name: Optional[str],
        is_constructor: bool = False,
    ) -> Optional[FunctionMetadata]:
        """Extract metadata from a method node."""
        
        # Get method name
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        
        method_name = name_node.text.decode("utf-8")
        
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
            name=method_name,
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
        for child in root.children:
            if child.type == "import_declaration":
                import_text = source_text[child.start_byte:child.end_byte]
                # Clean up: "import org.foo.Bar;" -> "org.foo.Bar"
                import_text = import_text.replace("import", "").replace(";", "").strip()
                imports.append(import_text)
        return imports
    
    def _extract_calls(self, node: Node, source_text: str) -> list[str]:
        """Extract function/method calls from a method body."""
        calls = []
        
        def find_calls(n: Node):
            if n.type == "method_invocation":
                # Get the method name
                name_node = n.child_by_field_name("name")
                if name_node:
                    call_name = name_node.text.decode("utf-8")
                    if call_name not in calls:
                        calls.append(call_name)
            
            for child in n.children:
                find_calls(child)
        
        find_calls(node)
        return calls
    
    def calculate_complexity(self, code: str) -> int:
        """
        Calculate McCabe cyclomatic complexity for Java code.
        
        Complexity = 1 + number of decision points
        Decision points: if, else if, for, while, do, switch case, catch, &&, ||, ?:
        """
        complexity = 1  # Base complexity
        
        # Count decision keywords
        patterns = [
            r'\bif\s*\(',
            r'\belse\s+if\s*\(',
            r'\bfor\s*\(',
            r'\bwhile\s*\(',
            r'\bdo\s*\{',
            r'\bcase\s+',
            r'\bcatch\s*\(',
            r'&&',
            r'\|\|',
            r'\?[^?]',  # Ternary operator
        ]
        
        for pattern in patterns:
            complexity += len(re.findall(pattern, code))
        
        return complexity
