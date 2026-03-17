# LegacyLens Tests

This directory contains the `pytest` testing suite for the LegacyLens project.

## Contents
- **`test_analysis_modules.py`**: Tests for the static analysis and parsing modules.
- **`test_critic_bugs.py`**: Tests verifying the Critic model's ability to catch logic flaws, hallucinations, and syntax divergence.
- **`test_e2e_batch.py` & `test_e2e_flow.py`**: End-to-end testing of the pipeline (from extraction to verified generation).
- **`test_embeddings.py`**: Tests for the vectorization and context retrieval (RAG) functionality.
- **`test_parser.py`**: Tests ensuring codebase parsing and AST slicing work effectively across different languages.
- **`test_prompt_repetition.py` / `test_structured_feedback.py`**: Tests isolating specific prompt engineering and critic feedback loops.

To run the tests:
```bash
pytest tests/
```
