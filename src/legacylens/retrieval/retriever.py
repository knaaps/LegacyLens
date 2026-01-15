"""Retrieval pipeline: orchestrates parsing, embedding, and search."""

from pathlib import Path
from typing import Optional

from legacylens.embeddings.code_embedder import CodeEmbedder
from legacylens.parser.base import CodeParser, FunctionMetadata
from legacylens.parser.java_parser import JavaParser
from legacylens.parser.python_parser import PythonParser


class CodeRetriever:
    """Orchestrate code indexing and retrieval."""
    
    def __init__(self, db_path: str = "./legacylens_db"):
        """
        Initialize the retriever.
        
        Args:
            db_path: Path to store the vector database
        """
        self.embedder = CodeEmbedder(db_path=db_path)
        self.parsers: list[CodeParser] = [
            JavaParser(),
            PythonParser(),
        ]
    
    def _get_parser_for_file(self, file_path: Path) -> Optional[CodeParser]:
        """Get the appropriate parser for a file."""
        for parser in self.parsers:
            if parser.can_parse(file_path):
                return parser
        return None
    
    def index_file(self, file_path: Path) -> int:
        """
        Parse and index a single file.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Number of functions indexed
        """
        parser = self._get_parser_for_file(file_path)
        if not parser:
            return 0
        
        functions = parser.parse_file(file_path)
        if not functions:
            return 0
        
        for func in functions:
            self.embedder.store(func)
        
        return len(functions)
    
    def index_repository(
        self,
        repo_path: Path,
        extensions: Optional[list[str]] = None,
    ) -> dict:
        """
        Parse and index an entire repository.
        
        Args:
            repo_path: Path to the repository root
            extensions: Optional list of file extensions to include
                       (default: .java, .py)
            
        Returns:
            Statistics about the indexing process
        """
        if extensions is None:
            extensions = [".java", ".py"]
        
        stats = {
            "files_processed": 0,
            "functions_indexed": 0,
            "files_skipped": 0,
            "errors": [],
        }
        
        # Collect all functions first for batch processing
        all_functions: list[FunctionMetadata] = []
        
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            if file_path.suffix.lower() not in extensions:
                continue
            
            # Skip test files, vendor, node_modules, etc.
            path_str = str(file_path)
            if any(skip in path_str for skip in [
                "/test/", "/tests/", "__pycache__", "node_modules", "/vendor/"
            ]):
                stats["files_skipped"] += 1
                continue
            
            parser = self._get_parser_for_file(file_path)
            if not parser:
                stats["files_skipped"] += 1
                continue
            
            try:
                functions = parser.parse_file(file_path)
                all_functions.extend(functions)
                stats["files_processed"] += 1
            except Exception as e:
                stats["errors"].append(f"{file_path}: {str(e)}")
        
        # Batch store
        if all_functions:
            stats["functions_indexed"] = self.embedder.store_batch(all_functions)
        
        return stats
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        language: Optional[str] = None,
    ) -> list[dict]:
        """
        Search for code matching a query.
        
        Args:
            query: Natural language query or code snippet
            top_k: Number of results to return
            language: Optional filter ('java' or 'python')
            
        Returns:
            List of matching code snippets with metadata
        """
        results = self.embedder.search(query, top_k=top_k, language_filter=language)
        
        # Enhance results with formatted output
        for result in results:
            meta = result["metadata"]
            result["summary"] = (
                f"{meta['qualified_name']} ({meta['language']}) "
                f"- Complexity: {meta['complexity']}, Lines: {meta['line_count']}"
            )
        
        return results
    
    def get_context_for_explanation(
        self,
        query: str,
        top_k: int = 3,
    ) -> dict:
        """
        Get context for AI explanation (used by Writer agent).
        
        Args:
            query: Query about code
            top_k: Number of similar code snippets to include
            
        Returns:
            Context dict with code, static facts, and similar code
        """
        results = self.search(query, top_k=top_k)
        
        if not results:
            return {"error": "No matching code found"}
        
        primary = results[0]
        similar = results[1:] if len(results) > 1 else []
        
        # Extract static facts for grounding
        meta = primary["metadata"]
        static_facts = {
            "name": meta["qualified_name"],
            "language": meta["language"],
            "complexity": meta["complexity"],
            "line_count": meta["line_count"],
            "calls": meta.get("calls", "").split(",") if meta.get("calls") else [],
            "imports": meta.get("imports", "").split(",") if meta.get("imports") else [],
        }
        
        return {
            "code": primary["code"],
            "static_facts": static_facts,
            "similar_code": [s["code"] for s in similar],
            "file_path": meta["file_path"],
        }
    
    def get_stats(self) -> dict:
        """Get statistics about the indexed codebase."""
        return self.embedder.get_stats()
