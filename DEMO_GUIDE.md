# Faculty Demo Guide

## Quick Start

```bash
# Ensure PetClinic is indexed
legacylens index data/spring-petclinic

# Run the demo
python faculty_demo.py
```

## What It Demonstrates

### 1. AST Parsing & Indexing (📚)
- Tree-Sitter parsing of Java files
- Function metadata extraction (complexity, calls, imports)
- CodeBERT embedding generation

### 2. Semantic Search (🔍)
- Natural language query: "find owners by last name"
- Vector similarity matching (no keyword dependency)
- Top-K retrieval from ChromaDB

### 3. Hybrid Context Assembly (🧩)
- Deterministic call graph construction
- Context slicing (callers + callees)
- RAG fallback for missing relationships

### 4. Multi-Agent Verification (🤖)
- **Writer:** Drafts explanation using Groq/Ollama
- **Compositional Critic:**
  - Factual: Cross-references names vs AST
  - Completeness: Checks params/returns/side effects
  - Risk: Flags SQL injection, unsafe patterns
- **Regeneration Validator:** Reconstructs code from explanation (AST fidelity)

### 5. 3D CodeBalance Scoring (⚖️)
- **Energy:** Computational cost (loops, recursion)
- **Debt:** Maintainability (nesting, params, length)
- **Safety:** Security risks (injection, eval, hardcoded secrets)

## Expected Output

```
📚 STEP 1: AST Parsing & Indexing
────────────────────────────────────────────────────────────────────────────────
  Found 50 Java files
  Extracted 12 methods from OwnerController
  Stored 5 function embeddings

🔍 STEP 2: Semantic Search (RAG)
────────────────────────────────────────────────────────────────────────────────
  Query: "find owners by last name"
  
  Top 3 Semantic Matches:
  ┌──────┬───────────────────────────────┬────────────┐
  │ Rank │ Function                      │ Similarity │
  ├──────┼───────────────────────────────┼────────────┤
  │    1 │ processFindForm               │      0.847 │
  │    2 │ findPaginatedForOwnersLastName│      0.792 │
  │    3 │ findByLastName                │      0.731 │
  └──────┴───────────────────────────────┴────────────┘

🤖 STEP 4: Multi-Agent Verification
────────────────────────────────────────────────────────────────────────────────
  Verification Metrics:
  ┌────────────────┬────────┐
  │ Metric         │ Value  │
  ├────────────────┼────────┤
  │ Verified       │ ✓ PASS │
  │ Confidence     │ 95%    │
  │ Factual Check  │ ✓      │
  │ Completeness   │ 100%   │
  │ Fidelity (AST) │ 83%    │
  └────────────────┴────────┘
```

## Configuration

### Use Groq (Fast, Cloud)
```bash
# Create apikey.env with your Groq key
echo 'groq=gsk_your_key_here' > apikey.env

# Run demo
LLM_PROVIDER=groq python faculty_demo.py
```

### Use Ollama (Private, Local)
```bash
# Pull models
ollama pull deepseek-coder:6.7b
ollama pull qwen2.5-coder:7b

# Run demo (default)
python faculty_demo.py
```

## Troubleshooting

**Error: PetClinic not found**
```bash
cd data
git clone https://github.com/spring-projects/spring-petclinic
```

**Error: Model not found (Ollama)**
```bash
ollama serve &
ollama pull deepseek-coder:6.7b
```

**Low fidelity scores**
- Normal for small functions (<10 lines)
- AST similarity focuses on structure, not variable names
- Scores >70% indicate strong understanding
