# LegacyLens: Final Research-Backed Smart Hybrid Blueprint
*(Version: 1.0 - Final Synthesis as of Jan 22, 2026)*

**Author Notes:** This blueprint incorporates insights from Nytko, Sanas, Yang (C2AADL), Ala-Salmi (VAPU), and Schuts papers. It defines a defensible, novel architecture for legacy code comprehension.

---

## 1. Executive Summary

**Core Concept:** A "Smart Hybrid" pipeline that prioritizes deterministic structural analysis (call graphs, slicing) and falls back to semantic search (RAG) only when necessary. This combination addresses the weakness of pure semantic approaches (missing structure) while handling scale better than pure static analysis.

**Novel Contributions:**
1.  **Multi-Agent Verification:** A "Writer-Critic-Finalizer" loop to ensure factual accuracy and readability.
2.  **3D CodeBalance Matrix:** Evaluates code on Energy Efficiency, Technical Debt, and Safety Risk.
3.  **Regeneration Validation:** Uses LLM-based code regeneration to verify the fidelity of explanations.

**Target Metrics:**
-   Accuracy: 87% (vs. ~64% baseline)
-   Uplift over ZSL: 23%
-   Regeneration Fidelity: 78%

---

## 2. Architecture Overview

### 2.1 The Pipeline
1.  **Phase 0: Repo Partitioning (Schuts-Inspired):** Divide large repositories into manageable modules (<50k LOC) using graph clustering.
2.  **Phase 1: Intelligent Context Assembly:**
    *   **Primary:** Deterministic Slicing (Target function + Parent class + 1-hop Callers/Callees + Imports).
    *   **Fallback:** Vector Retrieval (RAG) if context < 20k tokens.
3.  **Phase 2: Hint Enrichment (CLaRa + C2AADL):**
    *   Inject static analysis facts (complexity, unused vars).
    *   Detect runtime patterns (threading, async) and domain keywords.
    *   Generate "Must-Cover Questions" for the Writer.
4.  **Phase 3: Multi-Agent Verification:**
    *   **Writer Agent (Temp=0.3):** Drafts explanation.
    *   **Compositional Critic (Temp=0.0):** Verifies sub-properties (Factual Accuracy, Completeness, Risk Awareness).
    *   **Finalizer Agent (Temp=0.5):** Polishes for readability.
5.  **Phase 4: CodeBalance Analysis (3D):**
    *   Scores Energy, Debt, and Safety (0-10 scale).
6.  **Phase 5: Regeneration Validation:**
    *   Regenerate code from explanation -> Compare with original -> Pass if similarity > 70%.

---

## 3. Detailed Implementation Plan

### 3.1 Phase 0: Repo Partitioning
*(Status: Future Work)*
-   Use `networkx` to build a dependency graph of the repository.
-   Cluster files into modules based on connectivity.
-   Ensure no single module exceeds 50k LOC.

### 3.2 Phase 1: Context Assembly
*(Status: Implemented)*
-   **Parsers:** Tree-sitter for Java and Python.
-   **Call Graph:** In-memory bidirectional graph of function calls.
-   **Slicing:** Extract target function, callers, and callees.
-   **Fallback:** ChromaDB vector search for semantic relevance.

### 3.3 Phase 2: Hint Enrichment
*(Status: Pending)*
-   **Runtime Patterns:** Detect `Thread`, `synchronized`, `async/await`, `Future`.
-   **Risk Flags:** Detect potential SQL injection, resource leaks.
-   **Must-Cover:** Questions like "How is thread safety handled?" or "What are the input validation rules?".

### 3.4 Phase 3: Multi-Agent Loop
*(Status: Partially Implemented)*
-   **Writer:** Current implementation uses `deepseek-coder:6.7b`.
-   **Critic:** Needs upgrade to "Compositional" mode (separate checks for facts, completeness, risk).
-   **Finalizer:** Needs implementation (currently just Writer -> Critic loop).

### 3.5 Phase 4: CodeBalance
*(Status: Implemented)*
-   **Energy:** Call depth, loops, recursion, heavy operations.
-   **Debt:** Function length, parameter count, nesting depth, lack of comments.
-   **Safety:** Dangerous patterns (eval, shell injection, swallowed exceptions).

### 3.6 Phase 5: Regeneration Validation
*(Status: Pending)*
-   **Concept:** If the explanation is good, an LLM should be able to write the code back from it.
-   **Metric:** AST-based code similarity (not just text overlap).
-   **Threshold:** > 70% structural match required for "High Fidelity".

---

## 4. Success Metrics & Validation

| Metric | Target | Measurement |
| :--- | :--- | :--- |
| **Accuracy** | 87% | BLEU scores vs expert annotations |
| **Uplift** | 23% | Improvement over Zero-Shot Learning (ZSL) baseline |
| **Fidelity** | 78% | Regeneration similarity score |
| **Hallucation Catch Rate** | >70% | Percentage of errors caught by Critic agent |

---

## 5. Thesis Defense Strategy

**Why Hybrid?** Pure semantic search misses structural context (Nytko). Pure static analysis doesn't scale. Hybrid balances both.
**Why Multi-Agent?** LLMs hallucinate. A separate Verifier (Reference: VAPU) significantly reduces error rates.
**Why CodeBalance?** Maintainability is multi-dimensional. Adding "Energy" and "Safety" makes it 3D and more relevant for modern/legacy systems.
