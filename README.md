# LegacyLens

> **Intelligent Context Engineering for Legacy Code Comprehension**

![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Status](https://img.shields.io/badge/status-research_preview-orange.svg)

**LegacyLens** is a research-backed developer tool designed to demystify complex, undocumented legacy codebases. Unlike standard AI coding assistants that rely on potential "hallucinations" or purely semantic retrieval, LegacyLens employs a **Smart Hybrid Pipeline**: combining deterministic static analysis (Call Graphs, ASTs) with a **Multi-Agent Verification Loop**: to produce accurate, structurally sound explanations.

---

##  Key Features

###  Smart Hybrid Context
LegacyLens prioritizes structural understanding over simple text matching:
1.  **Deterministic Slicing:** Retrieves the exact code, its direct callers, and callees using an in-memory call graph.
2.  **RAG Fallback:** Seamlessly blends in semantic search results from **ChromaDB** only when deterministic context is insufficient.

###  Multi-Agent Verification
LegacyLens orchestrates a **Writer-Critic Loop** with **Compositional Verification**:
-   **Writer Agent:** Drafts a fluent, human-readable explanation using **Hybrid LLMs** (Groq cloud or local Ollama).
-   **Compositional Critic:** Rigorously verifies the draft using a 3-layer audit:
    1.  **Factual:** Cross-references names against the AST to catch hallucinations.
    2.  **Completeness:** Ensures coverage of params, returns, and side effects.
    3.  **Risk:** Flags unmentioned safety issues (e.g., SQL injection).
-   **Regeneration Validator:** Proves understanding by reconstructing the code from the explanation (AST fidelity check).

###  3D CodeBalance Score
Assessing code health scores of every function on three critical axes (0-10 scale):
-   **Energy:** Computational cost (loops, recursion, complexity).
-   **Debt:** Maintainability burden (nesting depth, parameter count, length).
-   **Safety:** Security risks (SQL injection patterns, unsafe shell usage, swallowed exceptions).

---

##  Architecture

The pipeline moves beyond simple RAG by enforcing structural rigor and multi-stage verification:

```ascii
┌──────────────┐      ┌───────────────────────────┐      ┌────────────────────┐
│  Legacy Code │ ──►  │ Phase 1: In-Memory Index  │ ──►  │ Phase 1: Embeddings│
│              │      │ (Call Graph + AST)        │      │ (CodeBERT + Chroma)│
└──────────────┘      └───────────────────────────┘      └──────────┬─────────┘
                                                                    │
┌─────────────────────────────┐                                     ▼
│ Phase 3: Multi-Agent Loop   │     ┌─────────────────────────────────────┐
│ ┌────────┐    ┌────────┐    │     │ Phase 2: Smart Context Assembly     │
│ │ Writer │◄──►│ Critic │    │◄─── │ • Primary: Deterministic Call Graph │
│ └────────┘    └────────┘    │     │ • Backup: Vector RAG                │
│      │ Passed?              │     └─────────────────────────────────────┘
│      ▼                      │
│ ┌───────────┐               │
│ │ Regen Val.│ (AST Check)   │
│ └─────┬─────┘               │
└───────┼─────────────────────┘
        │
        ▼
┌───────────────────┐      ┌───────────────────────┐
│ Verified Output   │ ◄──  │ Phase 4: CodeBalance  │
│                   │      │ (3D Health Metrics)   │
└───────────────────┘      └───────────────────────┘
```

---

##  Quick Start

### Prerequisites
*   **Python 3.10+**
*   **Ollama** (for local privacy) OR **Groq API Key** (for speed)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/knaaps/LegacyLens
    cd LegacyLens
    ```

2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # Linux/Mac
    # .\venv\Scripts\activate # Windows
    ```

3.  **Install in editable mode:**
    ```bash
    pip install -e .
    ```

### Setup AI Backend

 LegacyLens supports a **Hybrid Mode**:

**Option A: 100% Local (Privacy Focused)**
   - Install [Ollama](https://ollama.com).
   - Pull models: `ollama pull deepseek-coder:6.7b` and `ollama pull qwen2.5-coder:7b`.
   - *No configuration needed — this is the default.*

**Option B: Groq Cloud (Speed Focused)**
   - Get a free API key from [console.groq.com](https://console.groq.com/).
   - Create `apikey.env` in the project root:
     ```env
     groq=gsk_your_key_here
     ```
   - Run with `LLM_PROVIDER=groq`.

---

##  Usage

### 1. Index a Repository
Build the static analysis graph and vector store.
```bash
# Index a Java project
legacylens index data/spring-petclinic

# Index a Python project
legacylens index my-python-proj/
```

### 2. Query the Codebase (RAG)
Find code using natural language.
```bash
legacylens query "where is user input validated?"
```

### 3. Explain & Verify (Core Feature)
Trigger the Multi-Agent loop to explain a specific function.
```bash
# Local Mode
legacylens explain "processFindForm"

# Cloud/Fast Mode
LLM_PROVIDER=groq legacylens explain "processFindForm"
```

**Sample Output:**
>  **Verified** (Confidence: 100%) | Fidelity: 83%
>
> **Explanation:** The `processFindForm` method handles GET requests... [Detailed description]
>
> **Critique:**
> - Factual: ✓ | Completeness: 100% | Risks Flagged: 0
>
> **CodeBalance:**
> -  Energy: [1/10] (Efficient)
> -  Debt: [4/10] (Moderate nesting)
> -  Safety: [8/10] (Risk: Unvalidated input)

### 4. View Stats
Check codebase size and database status.
```bash
legacylens stats
```

---

##  Project Structure

- `src/legacylens/agents/`: Multi-agent orchestration (Writer, Critic, Finalizer).
- `src/legacylens/analysis/`: Static analysis logic (Call Graph, CodeBalance, Complexity).
- `src/legacylens/embeddings/`: CodeBERT vector integration.
- `src/legacylens/parser/`: Tree-sitter parsers for Java and Python.
- `src/legacylens/retrieval/`: Hybrid retrieval engine.

---

##  Research Goals

LegacyLens aims to solve key challenges in automated code comprehension:
1.  **Hallucination Reduction:** By feeding the LLM verifiable facts derived from static analysis (ASTs).
2.  **Context Precision:** Avoiding "context window overflow" by intelligently slicing only relevant code.
3.  **Sustainability:** Encouraging energy-efficient and maintainable code through the 3D CodeBalance metric.

For detailed research plans and architecture blueprints, see [blueprint.md](blueprint.md).
For project progress and timelines, see [Tracking.md](Tracking.md).

---

## License

MIT License. See [LICENSE](LICENSE) for details.
