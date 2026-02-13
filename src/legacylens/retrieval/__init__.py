"""Retrieval Module — Orchestrates parsing, embedding, and search.

Combines the Parser and Embeddings modules into a single pipeline:
    1. Parse source files → extract function metadata
    2. Embed functions → store in ChromaDB
    3. Search → find similar code by natural language query

Usage:
    from legacylens.retrieval import CodeRetriever

    retriever = CodeRetriever(db_path="./my_db")
    retriever.index_repository(Path("./my_repo"))
    results = retriever.search("find user validation")
"""

from legacylens.retrieval.retriever import CodeRetriever

__all__ = ["CodeRetriever"]
