"""Code embeddings using CodeBERT and ChromaDB for vector storage."""

from pathlib import Path
from typing import Optional

import chromadb
import torch
from chromadb.config import Settings
from transformers import AutoModel, AutoTokenizer

from legacylens.parser.base import FunctionMetadata


class CodeEmbedder:
    """Generate and store code embeddings using CodeBERT + ChromaDB."""
    
    # CodeBERT produces 768-dimensional embeddings
    EMBEDDING_DIM = 768
    MODEL_NAME = "microsoft/codebert-base"
    
    def __init__(
        self,
        db_path: str = "./legacylens_db",
        collection_name: str = "codebase",
    ):
        """
        Initialize the embedder.
        
        Args:
            db_path: Path to persist ChromaDB data
            collection_name: Name of the vector collection
        """
        self._db_path = Path(db_path)
        self._collection_name = collection_name
        
        # Lazy loading - only load when needed
        self._tokenizer: Optional[AutoTokenizer] = None
        self._model: Optional[AutoModel] = None
        self._chroma_client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[chromadb.Collection] = None
    
    def _ensure_model_loaded(self) -> None:
        """Load CodeBERT model if not already loaded."""
        if self._tokenizer is None:
            print(f"Loading {self.MODEL_NAME}...")
            self._tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
            self._model = AutoModel.from_pretrained(self.MODEL_NAME)
            self._model.eval()  # Set to evaluation mode
            print("Model loaded.")
    
    def _ensure_db_connected(self) -> None:
        """Connect to ChromaDB if not already connected."""
        if self._chroma_client is None:
            self._db_path.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(
                path=str(self._db_path),
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._chroma_client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},  # Use cosine similarity
            )
    
    def embed_code(self, code: str) -> list[float]:
        """
        Generate embedding for a code snippet.
        
        Args:
            code: Source code string
            
        Returns:
            768-dimensional embedding as a list of floats
        """
        self._ensure_model_loaded()
        
        # Tokenize (truncate to 512 tokens max)
        tokens = self._tokenizer(
            code,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        
        # Generate embedding (no gradient needed)
        with torch.no_grad():
            outputs = self._model(**tokens)
            # Use [CLS] token embedding (first token)
            embedding = outputs.last_hidden_state[:, 0, :].squeeze().numpy()
        
        return embedding.tolist()
    
    def store(self, metadata: FunctionMetadata) -> str:
        """
        Store a function's embedding in ChromaDB.
        
        Args:
            metadata: Function metadata including code
            
        Returns:
            The ID used to store the embedding
        """
        self._ensure_db_connected()
        
        # Generate embedding
        embedding = self.embed_code(metadata.code)
        
        # Create unique ID
        doc_id = f"{metadata.file_path}::{metadata.qualified_name}::{metadata.start_line}"
        
        # Store in ChromaDB
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[metadata.code],
            metadatas=[metadata.to_dict()],
        )
        
        return doc_id
    
    def store_batch(self, functions: list[FunctionMetadata], batch_size: int = 32) -> int:
        """
        Store multiple functions in batches.
        
        Args:
            functions: List of function metadata
            batch_size: Number of embeddings to process at once
            
        Returns:
            Number of functions stored
        """
        self._ensure_db_connected()
        self._ensure_model_loaded()
        
        stored = 0
        for i in range(0, len(functions), batch_size):
            batch = functions[i:i + batch_size]
            
            ids = []
            embeddings = []
            documents = []
            metadatas = []
            
            for func in batch:
                doc_id = f"{func.file_path}::{func.qualified_name}::{func.start_line}"
                embedding = self.embed_code(func.code)
                
                ids.append(doc_id)
                embeddings.append(embedding)
                documents.append(func.code)
                metadatas.append(func.to_dict())
            
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            
            stored += len(batch)
            print(f"Stored {stored}/{len(functions)} functions...")
        
        return stored
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        language_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Search for similar code by query.
        
        Args:
            query: Natural language query or code snippet
            top_k: Number of results to return
            language_filter: Optional filter by language ('java', 'python')
            
        Returns:
            List of results with code, metadata, and distance
        """
        self._ensure_db_connected()
        
        # Embed the query
        query_embedding = self.embed_code(query)
        
        # Build where filter if language specified
        where_filter = None
        if language_filter:
            where_filter = {"language": language_filter}
        
        # Search
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        
        # Format results
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "code": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        
        return formatted
    
    def get_stats(self) -> dict:
        """Get statistics about the stored embeddings."""
        self._ensure_db_connected()
        return {
            "total_functions": self._collection.count(),
            "collection_name": self._collection_name,
            "db_path": str(self._db_path),
        }
    
    def clear(self) -> None:
        """Clear all stored embeddings."""
        self._ensure_db_connected()
        self._chroma_client.delete_collection(self._collection_name)
        self._collection = self._chroma_client.create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
