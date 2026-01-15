#!/usr/bin/env python3
"""
LegacyLens Phase 1 Demo Script
==============================

This script demonstrates the complete RAG pipeline:
1. Parse code (Java + Python)
2. Generate embeddings with CodeBERT
3. Store in ChromaDB
4. Query and explain code using AI

Run: python demo.py
"""

import subprocess
import sys
from pathlib import Path

# Colors for terminal output
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def run(cmd: str, capture: bool = False) -> str:
    """Run a shell command."""
    print(f"{BLUE}$ {cmd}{RESET}")
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    if capture:
        return result.stdout
    return ""


def section(title: str):
    """Print a section header."""
    print(f"\n{BOLD}{GREEN}{'='*60}{RESET}")
    print(f"{BOLD}{GREEN}  {title}{RESET}")
    print(f"{BOLD}{GREEN}{'='*60}{RESET}\n")


def main():
    base_dir = Path(__file__).parent
    
    print(f"""
{BOLD}╔═══════════════════════════════════════════════════════════╗
║          LegacyLens - Phase 1 Demo                        ║
║  AI-Powered Legacy Code Understanding with Verification   ║
╚═══════════════════════════════════════════════════════════╝{RESET}
""")

    # Step 1: Show current stats
    section("1. Current Database Status")
    run("./venv/bin/legacylens stats")

    # Step 2: Create Python sample if not exists
    section("2. Creating Python Sample Code")
    python_sample = base_dir / "sample_python"
    python_sample.mkdir(exist_ok=True)
    
    sample_code = '''"""Sample Python module for LegacyLens demo."""

import json
from typing import List, Optional


class DataProcessor:
    """Process and transform data records."""
    
    def __init__(self, config: dict):
        self.config = config
        self.cache = {}
    
    def validate_record(self, record: dict) -> bool:
        """
        Validate a data record against schema.
        
        Returns True if valid, False otherwise.
        """
        required_fields = self.config.get("required_fields", [])
        
        for field in required_fields:
            if field not in record:
                return False
            if record[field] is None or record[field] == "":
                return False
        
        return True
    
    def transform_records(self, records: List[dict]) -> List[dict]:
        """
        Transform a batch of records.
        
        Applies validation and caching for efficiency.
        """
        results = []
        
        for record in records:
            record_id = record.get("id")
            
            # Check cache first
            if record_id and record_id in self.cache:
                results.append(self.cache[record_id])
                continue
            
            # Validate
            if not self.validate_record(record):
                continue
            
            # Transform
            transformed = {
                "id": record_id,
                "data": json.dumps(record),
                "processed": True,
            }
            
            # Cache result
            if record_id:
                self.cache[record_id] = transformed
            
            results.append(transformed)
        
        return results
    
    def clear_cache(self) -> int:
        """Clear the cache and return count of cleared items."""
        count = len(self.cache)
        self.cache = {}
        return count


def calculate_statistics(data: List[float]) -> Optional[dict]:
    """
    Calculate basic statistics for a list of numbers.
    
    Returns None if data is empty.
    """
    if not data:
        return None
    
    n = len(data)
    total = sum(data)
    mean = total / n
    
    # Calculate variance
    variance = sum((x - mean) ** 2 for x in data) / n
    std_dev = variance ** 0.5
    
    return {
        "count": n,
        "sum": total,
        "mean": mean,
        "min": min(data),
        "max": max(data),
        "std_dev": std_dev,
    }
'''
    
    sample_file = python_sample / "processor.py"
    sample_file.write_text(sample_code)
    print(f"Created: {sample_file}")
    print(f"\n{YELLOW}Sample code preview:{RESET}")
    print("-" * 40)
    lines = sample_code.split("\n")[:25]
    for i, line in enumerate(lines, 1):
        print(f"{i:3}: {line}")
    print("...")

    # Step 3: Index Python code
    section("3. Indexing Python Sample Code")
    run(f"./venv/bin/legacylens index {python_sample}")

    # Step 4: Query Python code
    section("4. Querying Python Code")
    run('./venv/bin/legacylens query "validate record" -k 2')

    # Step 5: Query Java code (from PetClinic)
    section("5. Querying Java Code (Spring PetClinic)")
    run('./venv/bin/legacylens query "find owner by name" -k 2')

    # Step 6: AI Explanation (requires Ollama)
    section("6. AI-Powered Explanation")
    print(f"{YELLOW}Note: This requires Ollama to be running with deepseek-coder:6.7b{RESET}\n")
    run('./venv/bin/legacylens explain "transform_records"')

    # Summary
    section("Demo Complete!")
    print(f"""
{BOLD}What was demonstrated:{RESET}

  ✓ Parser:      Extracted functions from Java + Python code
  ✓ Embeddings:  Generated semantic vectors with CodeBERT  
  ✓ Storage:     Persisted to ChromaDB vector database
  ✓ Retrieval:   Found relevant code via semantic search
  ✓ Explanation: Generated AI explanation using Ollama

{BOLD}Commands available:{RESET}

  legacylens index <path>     Index a repository
  legacylens query <text>     Search for code
  legacylens explain <text>   Get AI explanation
  legacylens stats            Show database stats

{BOLD}Next Steps (Phase 2):{RESET}

  - Writer-Critic verification loop
  - Confidence scoring
  - Dependency graph visualization
""")


if __name__ == "__main__":
    main()
