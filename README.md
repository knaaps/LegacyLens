# LegacyLens

> **Intelligent Context Engineering for Legacy Code Comprehension**

![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Status](https://img.shields.io/badge/status-research_preview-orange.svg)

**LegacyLens** is a research-backed developer tool designed to demystify complex, undocumented legacy codebases. Unlike standard AI coding assistants that rely on potential "hallucinations" or purely semantic retrieval, LegacyLens employs a **Smart Hybrid Pipeline**—combining deterministic static analysis (Call Graphs, ASTs) with a **Multi-Agent Verification Loop**—to produce accurate, structurally sound explanations.

---

## 🚀 Key Features

### 🧠 Smart Hybrid Context
LegacyLens prioritizes structural understanding over simple text matching:
1.  **Deterministic Slicing:** Retrieves the exact code, its direct callers, and callees using an in-memory call graph.
2.  **RAG Fallback:** Seamlessly blends in semantic search results from **ChromaDB** only when deterministic context is insufficient.

### 🕵️ Multi-Agent Verification
Stop trusting generated text blindly. LegacyLens orchestrates a **Writer-Critic Loop**:
-   **Writer Agent:** Drafts a fluent, human-readable explanation.
-   **Critic Agent:** Rigorously verifies the draft against source code, flagging hallucinations and missing safety warnings.
-   **Orchestrator:** Manages the feedback loop until the explanation passes verification thresholds.

### ⚖️ 3D CodeBalance Score
Assessing code health isn't one-dimensional. LegacyLens scores every function on three critical axes (0-10 scale):
-   **⚡ Energy:** Computational cost (loops, recursion, complexity).
-   **🔧 Debt:** Maintainability burden (nesting depth, parameter count, length).
-   **🛡️ Safety:** Security risks (SQL injection patterns, unsafe shell usage, swallowed exceptions).

---

## 🛠️ Architecture

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
│ │ Result    │               │
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

## ⚡ Quick Start

### Prerequisites
*   **Python 3.10+**
*   **Ollama** (Required for local LLM inference)

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
LegacyLens runs **100% locally** using Ollama to ensure data privacy and zero cost.

```bash
# Install Ollama (Linux/Mac)
curl -fsSL https://ollama.com/install.sh | sh

# Start the server
ollama serve &

# Pull required models
ollama pull deepseek-coder:6.7b  # Optimized for reasoning/coding
ollama pull qwen2.5-coder:7b     # Optimized for instruction following
```

---

## 📖 Usage

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
legacylens explain "processFindForm"
```

**Sample Output:**
> ✅ **Verified** (Confidence: 85%)
>
> **Explanation:** The `processFindForm` method handles GET requests... [Detailed description]
>
> **CodeBalance:**
> - ⚡ Energy: [1/10] (Efficient)
> - 🔧 Debt: [4/10] (Moderate nesting)
> - 🛡️ Safety: [8/10] (Risk: Unvalidated input)

### 4. View Stats
Check codebase size and database status.
```bash
legacylens stats
```

---

## 📂 Project Structure

- `src/legacylens/agents/`: Multi-agent orchestration (Writer, Critic, Finalizer).
- `src/legacylens/analysis/`: Static analysis logic (Call Graph, CodeBalance, Complexity).
- `src/legacylens/embeddings/`: CodeBERT vector integration.
- `src/legacylens/parser/`: Tree-sitter parsers for Java and Python.
- `src/legacylens/retrieval/`: Hybrid retrieval engine.

---

## 🔬 Research Goals

LegacyLens aims to solve key challenges in automated code comprehension:
1.  **Hallucination Reduction:** By feeding the LLM verifiable facts derived from static analysis (ASTs).
2.  **Context Precision:** Avoiding "context window overflow" by intelligently slicing only relevant code.
3.  **Sustainability:** Encouraging energy-efficient and maintainable code through the 3D CodeBalance metric.

For detailed research plans and architecture blueprints, see [blueprint.md](blueprint.md).
For project progress and timelines, see [Tracking.md](Tracking.md).

---

## License

MIT License. See [LICENSE](LICENSE) for details.
