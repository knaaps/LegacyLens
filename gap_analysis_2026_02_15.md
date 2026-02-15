# Gap Analysis Report
**Date:** February 15, 2026
**Target:** March 17, 2026 Submission

## 1. Executive Summary
The LegacyLens core pipeline (Parser → Hybrid Context → Writer/Critic → CodeBalance) is **functional and feature-complete for Phase 1**. Recent sprints successfully delivered the Compositional Critic, Regeneration Validation (with AST similarity), and local/cloud LLM abstraction.

However, to meet the "Smart Hybrid" thesis defensibility, **Phase 2 (Hint Enrichment)** and **Phase 3 (Finalizer)** are critical missing pieces. The system currently generates *verified* explanations but lacks *depth* regarding runtime behavior (concurrency) and may lack *polish* (readability).

**Overall Status:** 🟢 On Track (with tight schedule for Week 8)

---

## 2. Component Analysis

### ✅ Completed / Healthy
| Component | Status | Notes |
| :--- | :--- | :--- |
| **Parser & Indexer** | 🟢 Done | Tree-sitter + ChromaDB working robustly. |
| **Hybrid Context** | 🟢 Done | Call Graph + RAG fallback logic operational. |
| **Writer Agent** | 🟢 Done | Drafts explanations effectively (Temp 0.3). |
| **Critic Agent** | 🟢 Done | **Just Upgraded.** Now Compositional (Facts/Completeness/Risk) + JSON output + Caching. |
| **Regeneration** | 🟢 Done | **Just Upgraded.** AST-based validation with "Exact Equivalent" prompting. |
| **CodeBalance** | 🟢 Done | 3D Scoring (Energy/Debt/Safety) implemented. |

### ⚠️ Critical Gaps (Week 8 Scope)
These features are necessary to support the research claims in the blueprint.

#### 1. Runtime Pattern Detection (Hint Enrichment)
- **Gap:** The system is "static-blind" to runtime behaviors like concurrency, async flows, and transaction management.
- **Impact:** Explanations for complex legacy code (e.g., Spring Controllers using `CompletableFuture` or `synchronized` blocks) will miss the "why" of the implementation.
- **Requirement:** Add regex/AST detectors for `Thread`, `Runnable`, `synchronized`, `@Async`, `@Transactional`.

#### 2. Finalizer Agent
- **Gap:** The Writer/Critic loop focuses on *correctness*. The resulting verified explanation might be disjointed or dry.
- **Impact:** User experience suffers; "readability" metric in evaluation may be low.
- **Requirement:** A third agent (Temp 0.5) that takes the *Verified Explanation* and polishes it for flow/tone without altering facts.

#### 3. Token Counting & Context Budgeting
- **Gap:** Context assembly blindly adds neighbors and imports.
- **Impact:** Risk of overflowing context window on large files or deep call graphs.
- **Requirement:** Implement `tiktoken` (or approximate) counting to enforce the 20k token soft limit defined in Blueprint.

### ❌ Future / Evaluation Gaps (Week 9+ Scope)
- **Test Corpus:** No standardized set of 50 functions for benchmarking.
- **Ablation Harness:** No switch to strictly disable RAG or Static analysis for comparison limits.
- **Visualization:** CodeBalance scores are just text; need a radar chart or better UI representation.

---

## 3. Recommended Action Plan (Week 8)

**Goal:** Close the "Thesis Defensibility" items.

1.  **Implement `RuntimeContextAnalyzer`**:
    *   Create `src/legacylens/analysis/runtime_patterns.py`.
    *   Detects: Concurrency, Transactionality, Reflection.
    *   Injects finding into `static_facts` for the Writer.

2.  **Implement `FinalizerAgent`**:
    *   Create `src/legacylens/agents/finalizer.py`.
    *   Prompt: "Rewrite this verified explanation to be more engaging and professional. Do not change facts."

3.  **Add Token Safety**:
    *   Update `context_slicer.py` to truncate neighbors if context > limit.

4.  **Integration Test**:
    *   Run full pipeline on a complex multi-threaded method to verify `RuntimeContextAnalyzer` -> `Writer` -> `Critic` flow.
