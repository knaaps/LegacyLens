# LegacyLens

> **Intelligent Context Engineering for Legacy Code Comprehension**

LegacyLens is a research-backed developer tool that helps you understand complex, undocumented legacy codebases. Unlike standard AI tools that rely on "vibes," LegacyLens uses a **Smart Hybrid Pipeline**—combining deterministic static analysis with a **Multi-Agent Verification Loop**—to produce accurate, structurally sound explanations.

---

## 🚀 Key Innovations

| Feature                         | Description                            |
| :---                            |                                   :--- |
| **🧠 Smart Hybrid Context**     | Prioritizes deterministic code slicing (call graphs, dependencies) and falls back to RAG (Semantic Search) only when necessary. |

| **🕵️ Multi-Agent Verification** | Uses a **Writer-Critic-Finalizer** loop to verify factual accuracy, catching hallucinations before they reach you.                   |

| **⚖️ 3D CodeBalance**           | Scores code health on three axes: **Energy Efficiency**, **Technical Debt**, and **Safety Risk** (e.g., race conditions).           |

| **🔄 Regeneration Fidelity**    | Validates explanations by attempting to regenerate the original code from the explanation (aiming for >70% structural match).              |

---

## 🛠️ Architecture

The pipeline moves beyond simple RAG by enforcing structural rigor:

```ascii
┌──────────────┐      ┌───────────────────────────┐      ┌────────────────────┐
│  Legacy Code │ ──►  │ Phase 0: Repo Partitioning│ ──►  │ Phase 1: Indexing  │
└──────────────┘      │ (Schuts-style modules)    │      │ (Tree-sitter + AST)│
                      └───────────────────────────┘      └──────────┬─────────┘
                                                                    │
┌─────────────────────────────┐                                     ▼
│ Phase 3: Multi-Agent Loop   │     ┌─────────────────────────────────────┐
│ ┌────────┐    ┌────────┐    │     │ Phase 2: Smart Context Assembly     │
│ │ Writer │◄──►│ Critic │    │◄─── │ • Primary: Deterministic Slicing    │
│ └────────┘    └────────┘    │     │ • Fallback: Vector RAG (<20k tokens)│
│      │ Passed?              │     └─────────────────────────────────────┘
│      ▼                      │
│ ┌───────────┐               │
│ │ Finalizer │               │
│ └─────┬─────┘               │
└───────┼─────────────────────┘
        │
        ▼
┌───────────────────┐      ┌───────────────────────┐
│ Final Explanation │ ◄──  │ Phase 4: CodeBalance  │
│ + Safety Score    │      │ (Energy/Debt/Safety)  │
└───────────────────┘      └───────────────────────┘

```

---

## ⚡ Quick Start

### Prerequisites

* **Python 3.10+**
* **16GB RAM** (Recommended)
* **Ollama** (Required for the Agent Loop)

### 1. Installation

```bash
# Clone the repository
git clone [https://github.com/knaaps/LegacyLens](https://github.com/knaaps/LegacyLens)
cd LegacyLens

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate # Windows

# Install LegacyLens in editable mode
pip install -e .

```

### 2. Setup AI Backend (Ollama)

LegacyLens relies on local LLMs to ensure data privacy and zero cost.

```bash
# Install Ollama (Linux/Mac)
curl -fsSL [https://ollama.com/install.sh](https://ollama.com/install.sh) | sh

# Start the server
ollama serve &

# Pull the model (used for both Writer & Critic agents)
ollama pull deepseek-coder:6.7b

```

---

## Usage Commands

### `legacylens index <path>`

Parse and index a repository to build the Call Graph and Vector Store.

```bash
# Index a Java project (uses tree-sitter-java)
legacylens index data/spring-petclinic

# Index a Python project
legacylens index my-python-project/

```

**Output:**

```
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric            ┃ Value ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Modules Detected  │ 5     │
│ Functions Indexed │ 91    │
│ Graph Nodes       │ 450   │
└───────────────────┴───────┘

```

### `legacylens query <text>`

Search for code using natural language (RAG fallback).

```bash
legacylens query "where is the user input validated?" -k 3

```

### `legacylens explain <function_name>`

**The Core Feature.** Triggers the Multi-Agent Verification Loop.

```bash
legacylens explain "processFindForm"

```

**What happens next:**

1. **Context Assembly:** Fetches code + parent class + 1-hop callers.
2. **Writer Agent:** Drafts an explanation.
3. **Critic Agent:** Checks for hallucinations and missing safety flags (temp=0.0).
4. **CodeBalance:** Calculates Energy, Debt, and Safety scores.

**Sample Output:**

> **Status:** Verified (Confidence: 85%)
> **Safety Risk:** HIGH (Potential SQL Injection in Line 45)
> **Explanation:** The `processFindForm` method handles GET requests... [Detailed description verified by agents]

### `legacylens stats`

View database statistics and CodeBalance aggregates.

```bash
legacylens stats

```

---

## 📂 Project Structure

```
LegacyLens/
├── src/legacylens/
│   ├── analysis/             # Static Analysis & Slicing
│   │   ├── call_graph.py     # In-memory call graph
│   │   ├── context_slicer.py # Deterministic context assembly
│   │   ├── complexity.py     # McCabe/Halstead metrics
│   │   └── codebalance.py    # 3D Matrix (Energy, Debt, Safety)
│   ├── agents/               # Multi-Agent Logic
│   │   ├── writer.py         # Explainer (temp=0.3)
│   │   ├── critic.py         # Verifier (temp=0.0)
│   │   ├── finalizer.py      # Polisher
│   │   └── orchestrator.py   # Writer→Critic→Finalizer loop
│   ├── retrieval/            # Hybrid Retrieval (Graph + Vector)
│   └── main.py               # CLI Entry Point
├── data/                     # Test Repositories
└── pyproject.toml            # Dependencies

```

---

## 🗺️ Roadmap & Status

| Phase       | Feature                                  | Status            |
| ---         | ---                                      | ---               |
| **Phase 1** | Tree-sitter Parsing & Basic RAG          | ✅ Complete       |
| **Phase 2** | Smart Context (Hybrid Pipeline)          | 🚧 In Progress    |
| **Phase 2** | Multi-Agent Verification (Writer/Critic) | 🚧 In Progress    |
| **Phase 3** | 3D CodeBalance Matrix                    | ⏳ Planned (Feb)  |
| **Phase 4** | Regeneration Fidelity Check              | ⏳ Planned (Feb)  |

---

## 🔧 Configuration

By default, the database is stored in `./legacylens_db`.
To change the model or database path, set environment variables:

```bash
export LEGACYLENS_DB="/path/to/db"
export LEGACYLENS_MODEL="deepseek-coder:6.7b"

```

---

## License

MIT

```

```
