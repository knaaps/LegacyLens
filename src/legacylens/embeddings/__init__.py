"""Embeddings Module — Converts code into searchable vectors.

Uses Microsoft CodeBERT to generate 768-dimensional embeddings,
stored in ChromaDB for fast cosine similarity search.

Usage:
    from legacylens.embeddings import CodeEmbedder

    embedder = CodeEmbedder(db_path="./my_db")
    embedding = embedder.embed_code("def hello(): pass")
    results = embedder.search("find greeting function")
"""

from legacylens.embeddings.code_embedder import CodeEmbedder

__all__ = ["CodeEmbedder"]
