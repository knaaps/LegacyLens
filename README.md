<<<<<<< HEAD
# LegacyLens
=======
# LegacyLens

> **Understand legacy code through AI + static analysis verification**

LegacyLens helps developers comprehend unfamiliar codebases by combining semantic code search with AI-powered explanations, grounded in provable static analysis facts.

---

## Quick Start

```bash
# 1. Activate environment
cd /home/knaaps/Desktop/project/LegacyLens
source venv/bin/activate  # or: ./venv/bin/python ...

# 2. Index a repository
legacylens index data/spring-petclinic

# 3. Search for code
legacylens query "find owner by last name"

# 4. Get AI explanation (requires Ollama)
legacylens explain "processFindForm"
```

---

## Installation

### Prerequisites

- Python 3.10+
- 16GB RAM recommended
- Ollama (for AI explanations)

### Step 1: Python Environment

```bash
cd /home/knaaps/Desktop/project/LegacyLens

# Create virtual environment
python3 -m venv venv

# Install LegacyLens
./venv/bin/pip install -e .
```

### Step 2: Install Ollama (for AI explanations)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama (run in background)
ollama serve &

# Download the code model (~4GB)
ollama pull deepseek-coder:6.7b
```

---

## Commands

### `legacylens index <path>`

Parse and index a repository for searching.

```bash
# Index Java project
legacylens index data/spring-petclinic

# Index Python project  
legacylens index my-python-project/
```

**Output:**
```
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric            ┃ Value ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Files Processed   │ 30    │
│ Functions Indexed │ 91    │
│ Files Skipped     │ 17    │
│ Errors            │ 0     │
└───────────────────┴───────┘
```

### `legacylens query <text>`

Search for code by natural language or code snippet.

```bash
# Natural language query
legacylens query "save owner to database" -k 3

# Filter by language
legacylens query "validate" --language java
```

**Options:**
- `-k, --top-k`: Number of results (default: 5)
- `-l, --language`: Filter by `java` or `python`

### `legacylens explain <text>`

Get an AI-powered explanation of code.

```bash
legacylens explain "OwnerController"
```

**Output:**
1. Shows the retrieved code with syntax highlighting
2. Displays static analysis metadata (complexity, calls)
3. Generates a natural language explanation using the AI model

### `legacylens stats`

Show database statistics.

```bash
legacylens stats
```

---

## How It Works

```
                    ┌─────────────┐
                    │  Your Code  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Parser    │  ← tree-sitter (Java/Python)
                    │             │
                    │ Extracts:   │
                    │ • Functions │
                    │ • Complexity│
                    │ • Calls     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Embedder   │  ← CodeBERT (768-dim vectors)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  ChromaDB   │  ← Vector storage
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌─────▼─────┐     ┌─────▼─────┐
    │  query  │      │  explain  │     │   stats   │
    │         │      │           │     │           │
    │ Semantic│      │ RAG +     │     │ DB info   │
    │ search  │      │ Ollama    │     │           │
    └─────────┘      └───────────┘     └───────────┘
```

---

## Supported Languages

| Language | Parser | Complexity Metrics |
|----------|--------|-------------------|
| Java     | tree-sitter-java | McCabe (regex) |
| Python   | tree-sitter-python | radon + McCabe |

---

## Project Structure

```
LegacyLens/
├── src/legacylens/
│   ├── parser/           # Code parsing (tree-sitter)
│   │   ├── base.py       # Abstract interface
│   │   ├── java_parser.py
│   │   └── python_parser.py
│   ├── embeddings/       # CodeBERT + ChromaDB
│   │   └── code_embedder.py
│   ├── retrieval/        # Search pipeline
│   │   └── retriever.py
│   ├── generation/       # AI explanation
│   │   └── generator.py
│   └── main.py           # CLI entry point
├── tests/                # Unit tests
├── data/                 # Test repositories
│   ├── spring-petclinic/ # Java sample
│   └── apache-ant/       # Complex Java sample
├── demo.py               # Interactive demo
└── pyproject.toml        # Dependencies
```

---

## Testing

```bash
# Run all tests
./venv/bin/pytest tests/ -v

# Run parser tests only
./venv/bin/pytest tests/test_parser.py -v

# Run with coverage
./venv/bin/pytest tests/ --cov=legacylens
```

---

## Demo

Run the interactive demo to see all features:

```bash
python demo.py
```

This will:
1. Create a Python sample project
2. Index both Java and Python code
3. Demonstrate semantic search
4. Generate an AI explanation

---

## Configuration

### Database Location

By default, the vector database is stored in `./legacylens_db`. Override with:

```bash
legacylens --db-path /custom/path index my-repo/
```

### Model Selection

The default model is `deepseek-coder:6.7b`. To use a different Ollama model, modify `src/legacylens/generation/generator.py`:

```python
def generate_explanation(..., model: str = "codellama:7b"):
```

---

## Troubleshooting

### "No module named 'legacylens'"

```bash
./venv/bin/pip install -e .
```

### "Failed to connect to Ollama"

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve
```

### Slow first query

The first query downloads CodeBERT (~500MB). Subsequent queries are fast.

---

## Roadmap

### Phase 1 (Complete) ✅
- [x] Java + Python parsing
- [x] CodeBERT embeddings
- [x] ChromaDB storage
- [x] Semantic search
- [x] AI explanation

### Phase 2 (Next)
- [ ] Writer-Critic verification loop
- [ ] Confidence scoring
- [ ] Retry with feedback

### Phase 3 (Future)
- [ ] Dependency graph visualization
- [ ] Streamlit UI
- [ ] CodeBalance matrix

---

## License

MIT
>>>>>>> dfcc8b2 (interim production)
