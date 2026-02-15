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
  STEP 1   AST Parsing  (Tree-Sitter)

  Scanning PetClinic → 842 Java files found
  Parsed OwnerController → 12 methods

  Method                Lines   CC
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  OwnerController           3    1
  setAllowedFields          4    1
  findOwner                 7    2
  initCreationForm          4    1
  processCreationForm      11    2
  initFindForm              4    1
  ✓ Extracts functions, complexity, and call edges from AST

  ↵ Enter to continue...

  STEP 2   Semantic Search  (CodeBERT + ChromaDB)

  Loading CodeBERT & indexing functions...
  Indexed 12 embeddings

  Query: "find owner by last name"

    1. OwnerController.initFindForm        dist=0.0186
    2. OwnerController.initCreationForm    dist=0.0211
    3. OwnerController.OwnerController     dist=0.0216
  ✓ Finds relevant code by meaning, not keywords

  ↵ Enter to continue...

  STEP 3   Hybrid Context  (Call Graph + RAG)

  Building call graph...
  Graph nodes: 31
  Target: OwnerController.processFindForm
  Callers: 2  Callees: 2
    └─ calls → findPaginatedForOwnersLastName, addPaginationModel
  ✓ Deterministic 1-hop context assembled from call graph

  STEP 4   Multi-Agent Verification  (Writer → Critic → Regen)

  Provider: groq
  Running Writer → Critic → Regeneration...

╭────────────────────────────────────────────────────────────────────╮
│ Code Explanation...                                                │
╰────────────────────────────────────────────────────────────────────╯

  Verified:     PASS
  Confidence:   95%
  Iterations:   1
  Factual:      ✓
  Completeness: 100%
  Risks:        0
  Fidelity:     83%
  ✓ Explanation verified by Compositional Critic + Regeneration

  STEP 5   CodeBalance  (Energy / Debt / Safety)

  ⚡ Energy     ░░░░░░░░░░  0/10
  🔧 Debt       ████░░░░░░  4/10
  🛡️  Safety   ░░░░░░░░░░  0/10

  Grade: A  (total 4/30)
  ✓ 3-axis health score beyond cyclomatic complexity
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
