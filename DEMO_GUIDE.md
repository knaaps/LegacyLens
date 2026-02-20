# Faculty Demo Guide

## Quick Start

```bash
# Activate venv, then run:
python faculty_demo.py                     # Groq (default, fast)
LLM_PROVIDER=local python faculty_demo.py  # Ollama (private)
```

The demo is **self-contained** — it parses, indexes, searches, verifies, and
scores in a single run. No prior `legacylens index` step is required.

---

## Pipeline Overview

| Step | Module | Scope | What It Shows |
|------|--------|-------|---------------|
| **1 — AST Parsing** | Tree-Sitter | All 4 packages | Per-package breakdown, top-complexity methods |
| **2 — Semantic Search** | CodeBERT + ChromaDB | Full index | Two diverse queries across the whole codebase |
| **3 — Call Graph** | In-memory graph | Project-wide | Node/edge stats, most-connected functions, context tree |
| **4 — Multi-Agent** | Writer → Critic → Regen | `processFindForm` | Up to **5** revision loops with compositional checks |
| **5 — CodeBalance** | 3-axis scoring | Two functions | Side-by-side Energy / Debt / Safety comparison |

### Step 1 — Cross-Package Parsing

The demo parses the **entire** PetClinic source tree — all packages
(`owner`, `vet`, `system`, `model`, root classes) — not just one controller.
Output includes:

- A **package tree** showing file and method counts per package
- A **top-complexity table** ranking the most complex methods across the project

### Step 4 — Verification Loop (Deep Dive)

The orchestrator runs up to **5 iterations** (configurable via `MAX_ITER`):

```
Writer drafts explanation
    ↓
Compositional Critic checks:
    • Factual — cross-refs identifiers vs AST
    • Completeness — params / returns / side-effects
    • Risk — SQL injection, unsafe eval, etc.
    ↓
Verdict:  PASS → accept   |  REVISE → loop   |  FAIL → stop
    ↓
Regeneration Validator — reconstructs code from explanation (AST fidelity)
```

### Step 5 — Comparative Scoring

Two functions are scored side-by-side so the audience can compare code health:
- `processFindForm` — search handler with branching logic
- `processCreationForm` — form submission with validation

---

## Expected Output

```
╭──────────────────────────────────────────────────────────────────────────╮
│  LegacyLens  —  Faculty Demo                                            │
│                                                                          │
│  Target:  Spring PetClinic (full source)                                 │
│  LLM:     groq                                                           │
│  Loops:   5 max Writer→Critic iterations                                 │
╰──────────────────────────────────────────────────────────────────────────╯

─────────────────────────── STEP 1 ────────────────────────────
  AST Parsing  (Tree-Sitter)

  Scanning PetClinic source → 30 Java files

  petclinic
  ├── model    (3 files, 8 methods)
  ├── owner    (9 files, 45 methods)
  ├── system   (4 files, 6 methods)
  ├── vet      (6 files, 12 methods)
  └── (root)   (3 files, 2 methods)

  Total: 73 methods extracted

  ╭── Highest Complexity Methods ──╮
  │ Class.Method           Lines CC │
  │ OwnerController.proc…    18  4 │
  │ PetController.proc…      14  3 │
  │ …                              │
  ╰────────────────────────────────╯
  ✓ Parsed 30 files across 5 packages

─────────────────────────── STEP 2 ────────────────────────────
  Semantic Search  (CodeBERT + ChromaDB)

  Indexed 73 embeddings

  Query:  "find owner by last name"
    1. OwnerController.initFindForm        dist=0.0186
    2. OwnerController.initCreationForm    dist=0.0211

  Query:  "add a new pet to the clinic"
    1. PetController.initCreationForm      dist=0.0198
    2. PetController.processCreationForm   dist=0.0223

  ✓ Finds relevant code by meaning, not keywords
  ✓ Works across all packages

─────────────────────────── STEP 3 ────────────────────────────
  Hybrid Context  (Call Graph + RAG)

  ╭── Call Graph ──────────────────╮
  │ Nodes:  73  (functions)        │
  │ Edges:  120 (call rels)        │
  │ Most connected:                │
  │   • OwnerController.proc… → 5 │
  ╰────────────────────────────────╯

  Context slice for processFindForm:
  OwnerController.processFindForm
  ├── ↑ callers
  └── ↓ callees
      ├── findPaginatedForOwnersLastName
      └── addPaginationModel

  ✓ Deterministic 1-hop context from project-wide call graph

─────────────────────────── STEP 4 ────────────────────────────
  Multi-Agent Verification  (Writer → Critic → Regen)

  Provider:   groq
  Max loops:  5
  Target:     OwnerController.processFindForm

  ╭── Generated Explanation ───────╮
  │ This Spring MVC controller…    │
  ╰────────────────────────────────╯

  Verified       PASS
  Confidence     95%
  Iterations     1 / 5
  Factual        ✓ yes
  Completeness   100%
  Fidelity       83%
  ✓ Explanation verified by Compositional Critic + Regeneration

─────────────────────────── STEP 5 ────────────────────────────
  CodeBalance  (Energy / Debt / Safety)

  ╭─ processFindForm ──────────╮╭─ processCreationForm ────────╮
  │ ⚡ Energy   ████░░░░░░ 4/10 ││ ⚡ Energy   ███░░░░░░░ 3/10  │
  │ 🔧 Debt     ░░░░░░░░░░ 0/10 ││ 🔧 Debt     █░░░░░░░░░ 1/10  │
  │ 🛡️  Safety  ░░░░░░░░░░ 0/10 ││ 🛡️  Safety  ░░░░░░░░░░ 0/10  │
  │ Grade: A  (total 4/30)     ││ Grade: A  (total 4/30)       │
  ╰────────────────────────────╯╰──────────────────────────────╯
  ✓ Comparative view reveals relative code health

╭──────────────────────────────────────────────────────────────────────────╮
│  ✅  All 5 capabilities demonstrated successfully.                       │
╰──────────────────────────────────────────────────────────────────────────╯
```

---

## Configuration

### Groq (Cloud — Fast)

```bash
echo 'groq=gsk_your_key_here' > apikey.env
LLM_PROVIDER=groq python faculty_demo.py
```

### Ollama (Local — Private)

```bash
ollama pull deepseek-coder:6.7b
ollama pull qwen2.5-coder:7b
python faculty_demo.py  # or LLM_PROVIDER=local
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| PetClinic not found | `cd data && git clone https://github.com/spring-projects/spring-petclinic` |
| Ollama model missing | `ollama serve & ollama pull deepseek-coder:6.7b` |
| Low fidelity scores | Normal for small functions (<10 lines); ≥70% is strong |
| Critic always FAIL | Check Groq API key in `apikey.env`; ensure model is reachable |
