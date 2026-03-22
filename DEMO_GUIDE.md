# 🎓 LegacyLens: Final Faculty Demo Guide

Welcome to the **LegacyLens** showcase! This document serves as your definitive guide to demonstrating the platform's full capabilities to faculty, evaluators, or business stakeholders.

---

## 🌟 The Pitch

**LegacyLens** solves the "Developer Comprehension Gap" in legacy software. When developers inherit undocumented, monolithic codebases, traditional search tools fail. We provide:
1. **Intelligent Code Slicing (Call Graphs + AST)**
2. **Semantic Meaning Extraction (CodeBERT Embeddings)**
3. **Multi-Agent Hallucination Defense (Writer → Critic → Regen)**
4. **Interactive 3D Visual Analytics (Flask/Plotly/D3)**

By running this single script, you'll walk through a complete end-to-end pipeline on the industry-standard **Spring PetClinic** repository, demonstrating real-world scale and robustness.

---

## 🚀 Quick Start

Ensure your virtual environment is activated and the `data/spring-petclinic` repository is cloned.

```bash
# To run via Groq Cloud API (Recommended for live demos - extremely fast)
python scripts/faculty_demo.py

# To run via local Ollama models (For privacy & offline use)
LLM_PROVIDER=local python scripts/faculty_demo.py
```

The demo orchestrates every step dynamically in memory. **No prior indexing steps are required.**

---

## 🎬 Narrative Flow: What to Say & Show

Here is the exact step-by-step narrative to accompany the CLI execution.

### Step 1: Structural AST Parsing
* **The Action:** The script points an optimized Tree-Sitter parser at the entire PetClinic directory (30+ files across complex Spring MVC patterns).
* **The Talking Point:** *"Notice how we instantly map the application's DNA. We're not just reading text; we're building a structural AST namespace. We instantly extract cyclical complexity (CC) and call-edge relationships to find the riskiest, most complex methods across the entire monolith."*

### Step 2: Semantic AI Search
* **The Action:** The pipeline generates localized CodeBERT vector embeddings natively without cloud round-trips. It then executes human-language queries like *"find owner by last name"*.
* **The Talking Point:** *"Traditional 'grep' fails when variable names change. Here, we're using a dense vector space to find code by its **meaning and intent**. Notice how 'add a new pet' perfectly maps to the `processCreationForm` logic without direct keyword matches."*

### Step 3: Call Graph & RAG Slicing
* **The Action:** The system builds a deterministic, memory-resident contextual graph, mapping every single caller/callee relationship.
* **The Talking Point:** *"LLMs lose their minds when given too much code. We use graph traversal to build a 1-hop 'context slice'. We feed the AI the target function **plus exactly who calls it and who it calls**—nothing more, nothing less. This eliminates noise."*

### Step 4: Multi-Agent Critic Loop (The Crown Jewel)
* **The Action:** We dispatch our target function to the Writer Agent. It generates an explanation, which is instantly challenged by the Compositional Critic Agent.
* **The Talking Point:** *"This is our core innovation: **Multi-Agent Verification with Regeneration**. The Critic cross-references the Writer's explanation directly against the AST. Are all parameters mentioned? Are side effects listed? Did the AI hallucinate a database call? If the Critic rejects it, we loop up to 5 times. Finally, we score output using **Fidelity Regeneration**, asking an AI to write back code based solely on the explanation to prove it works."*

### Step 5: CodeBalance Scoring
* **The Action:** Two functions are scored side-by-side on Energy, Debt, and Safety risk axes.
* **The Talking Point:** *"Cyclomatic Complexity isn't enough anymore. We map structural health into an intuitive 3-axis KPI matrix. This helps management triage where to dedicate refactoring resources."*

### Step 6: 3D Visual Dashboard & Analytics
* **The Action:** The console instructs you to launch the visual interface.
* **The Talking Point:** *"CLI output is great for engineers, but management needs macro-visibility. Let's spin up the dashboard."*

➡️ **Action:** Open a new terminal and run:
```bash
legacylens dashboard
```
Showcase the **3D Risk Scatter Plot** and the **Interactive Risk Treemap Heatmap**. Emphasize that all node data was generated seamlessly by the pipeline you just ran!

---

## ⚙️ Advanced Tweaks & Troubleshooting

### Simulating Critic Failures
Want to prove the Critic works during the demo? Run with a "nervous" or "hallucinating" SOP variant:
```bash
python scripts/faculty_demo.py --sop cautious
```
*This loads a specialized prompt that makes the AI more likely to trigger a retry loop.*

### Changing Target Functions
Open `scripts/faculty_demo.py` and modify lines 47-48:
```python
TARGET_FN = "processFindForm"
TARGET_FN_2 = "processCreationForm"
```
You can switch these to any method in `data/spring-petclinic` to prove the system isn't hardcoded.

### Network / API Issues
If Groq is rate-limiting during the presentation:
1. Hit `Ctrl+C`.
2. Ensure you ran `ollama pull qwen2.5-coder:7b`.
3. Switch instantly: `LLM_PROVIDER=local python scripts/faculty_demo.py`.
