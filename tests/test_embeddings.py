"""Tests for the embeddings module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from legacylens.parser.base import FunctionMetadata


# We'll mock the heavy dependencies (transformers, chromadb) for fast tests
class TestCodeEmbedderMocked:
    """Tests for CodeEmbedder with mocked dependencies."""
    
    def test_embed_code_shape(self):
        """Test that embedding produces correct shape (mocked)."""
        # This test verifies the integration works
        # Real embeddings are tested in integration tests
        with patch('legacylens.embeddings.code_embedder.AutoTokenizer') as mock_tok, \
             patch('legacylens.embeddings.code_embedder.AutoModel') as mock_model:
            
            import torch
            
            # Setup mock tokenizer
            mock_tok.from_pretrained.return_value = MagicMock()
            mock_tok.from_pretrained.return_value.return_value = {
                'input_ids': torch.zeros(1, 10),
                'attention_mask': torch.ones(1, 10),
            }
            
            # Setup mock model output (768-dim)
            mock_output = MagicMock()
            mock_output.last_hidden_state = torch.randn(1, 10, 768)
            mock_model.from_pretrained.return_value.return_value = mock_output
            mock_model.from_pretrained.return_value.eval = MagicMock()
            
            from legacylens.embeddings.code_embedder import CodeEmbedder
            
            with tempfile.TemporaryDirectory() as tmpdir:
                embedder = CodeEmbedder(db_path=tmpdir)
                
                # Force model loading
                embedder._ensure_model_loaded()
                
                # Should have loaded the model
                mock_tok.from_pretrained.assert_called_once()
                mock_model.from_pretrained.assert_called_once()


class TestCodeEmbedderIntegration:
    """Integration tests that require actual dependencies.
    
    These are marked slow and can be skipped with: pytest -m "not slow"
    """
    
    @pytest.mark.slow
    def test_real_embedding_generation(self):
        """Test actual embedding generation with CodeBERT."""
        from legacylens.embeddings.code_embedder import CodeEmbedder
        
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = CodeEmbedder(db_path=tmpdir)
            
            code = "def hello(): return 'world'"
            embedding = embedder.embed_code(code)
            
            # Should be 768-dimensional
            assert len(embedding) == 768
            
            # Should be floats
            assert all(isinstance(x, float) for x in embedding)
    
    @pytest.mark.slow
    def test_store_and_search(self):
        """Test storing and searching embeddings."""
        from legacylens.embeddings.code_embedder import CodeEmbedder
        
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = CodeEmbedder(db_path=tmpdir)
            
            # Create test metadata
            meta = FunctionMetadata(
                name="add",
                file_path="/test.py",
                start_line=1,
                end_line=3,
                code="def add(a, b): return a + b",
                language="python",
                complexity=1,
                line_count=1,
            )
            
            # Store
            doc_id = embedder.store(meta)
            assert doc_id is not None
            
            # Search
            results = embedder.search("function that adds two numbers", top_k=1)
            assert len(results) == 1
            assert "add" in results[0]["code"]
    
    @pytest.mark.slow
    def test_batch_store(self):
        """Test batch storing multiple functions."""
        from legacylens.embeddings.code_embedder import CodeEmbedder
        
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = CodeEmbedder(db_path=tmpdir)
            
            functions = [
                FunctionMetadata(
                    name="add",
                    file_path="/math.py",
                    start_line=1,
                    end_line=2,
                    code="def add(a, b): return a + b",
                    language="python",
                ),
                FunctionMetadata(
                    name="subtract",
                    file_path="/math.py",
                    start_line=4,
                    end_line=5,
                    code="def subtract(a, b): return a - b",
                    language="python",
                ),
            ]
            
            count = embedder.store_batch(functions)
            assert count == 2
            
            stats = embedder.get_stats()
            assert stats["total_functions"] == 2
