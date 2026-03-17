# LegacyLens Scripts

This directory contains standalone automation, evaluation, and utility scripts used to interact with the LegacyLens core pipeline.

## Contents
- **`disk_cache.py`**: Implements a disk-based caching layer for storing and retrieving expensive LLM generation and verification results.
- **`faculty_demo.py`**: A demonstration script showcasing the end-to-end LegacyLens capabilities (parsing, embedding, explaining, and verifying code).
- **`metrics_scorer.py`**: Houses the logic to calculate evaluation metrics such as ROUGE scores, sequence fidelity, and accuracy/hallucination checks.
- **`run_ablation.py`**: The main execution orchestrator for running the ablation study across multiple configurations (zero-shot, pure RAG, repetition constraints).
- **`visualize_codebalance.py`**: Script for generating visualizations and scatter plots (often utilized by the dashboard or metrics tools).
