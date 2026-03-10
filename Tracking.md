# LegacyLens Comeback Tracker

**Project Pivot Notes:** Shifted from RAG-centralized to Hybrid AST + RAG for better determinism. Week off: Jan 23-29 (regressed connections). Restart: Jan 30, 2026.

**Overall Goal:** Hit March 17 submission. Track daily wins to rebuild familiarity.

## 📅 Roadmap & Milestones

### Historical Context
- **Jan 30:** Restarted work on Hybrid Pipeline.
- **Feb 4:** `context_engine.py` target (Missed/Superseded by `context_slicer.py`).
- **Feb 12:** Comprehensive Codebase Audit conducted.

### 📍 Current Status (As of Feb 12, 2026)
**Audit Finding:** Core pipeline is functional (Parser -> Embedder -> Hybrid Context -> Writer/Critic -> CodeBalance). However, critical thesis features are missing.

#### Scorecard:
| Module | Status | Notes |
| :--- | :--- | :--- |
| **Hybrid Context** | ✅ 80% | Slicing + RAG working. Needs token counting. |
| **Multi-Agent** | ✅ 90% | Writer+Critic working with Compositional Breakdown. |
| **CodeBalance** | ✅ 100% | **Implemented via interactive Web Dashboard.** |
| **Regeneration** | ✅ 100% | **Implemented via Tree-Sitter AST Similarity.** |

| **Hint Enrichment**| 🟡 50% | Compositional Critic handles risk/completeness. Runtime patterns next. |

### 🚀 Sprint Plan to Submission (Mar 17)

#### Week 7 (Feb 12-16): Critical Gap Fill
- [x] Implement **Regeneration Validation** (Phase 5) - *Thesis Critical*
- [x] Refactor Critic to **Compositional Mode** (Phase 3 novelty)
- [x] Add **LLM Provider Abstraction** (Groq support for speed)

#### Week 8 (Feb 17-23): Context & Polish
- [x] Add **Finalizer Agent** (Phase 3 completion)
- [x] Implement **Hint Enrichment** (Runtime patterns, "Must-Cover" questions)
- [ ] Add accurate **Token Counting**
- [ ] First full end-to-end test on Spring PetClinic

#### Week 9 (Feb 24 - Mar 2): Evaluation
- [x] Build Test Corpus (5 functions — PetClinic)
- [ ] Script BLEU/ROUGE scoring
- [x] Run Ablation Study (scaffold: `scripts/run_ablation.py` with 4 arms)

#### Week 10-11 (Mar 3-10): Writing & Demo
- [ ] LaTeX Report
- [ ] Demo Video
- [ ] User Study (3-5 devs)

#### Week 12 (Mar 10-17): Final Submission
- [ ] Final Polish & Code Freeze

---

## Daily Logs

### Day 1: January 30, 2026 (Phase 1 Start)
- **Re-Orient:** Reviewed old project notes.
- **Study Focus:** IBM RAG lab skim.
- **Apply Win:** Basic call graph working.
- **Momentum:** 7/10.

### ... [Gap in logs Jan 31 - Feb 11] ...

### Audit Day: February 12, 2026
- **Action:** Full codebase audit against blueprint.
- **Result:** Found strong core but missing thesis differentiators (Regeneration, Compositional Critic).
- **Adjustment:** Re-aligned roadmap to focus on purely thesis-critical features for next 2 weeks.

### Feature Sprint: February 14, 2026
- **Goal:** Close Phase 1 gaps (Regeneration, Critical Verification).
- **Result:**
    - **Hybrid LLM:** Added `ProviderFactory` (Groq/Ollama toggle).
    - **Regeneration:** Built `RegenerationValidator` using AST similarity (Tree-Sitter).
    - **Critic:** Refactored to `Compositional Critic` (Factual/Completeness/Risk checks).
    - **Verification:** 100% pass on synthetic bug injection and 5-function batch test.
- **Momentum:** 10/10. Phase 1 feature complete.

### Metrics Sprint: March 01, 2026
- **Goal:** Leverage advanced LLMs (Opus 4.6 style) for better regeneration metrics.
- **Result:**
    - **Prompt Repetition:** Integrated Leviathan et al. (2025) prompt duplication strategy.
    - **Code-Gen Wrapper:** Added `agents/utils.py` to boost AST fidelity natively during regeneration validation.
- **Momentum:** 10/10. Preparing for Ablation runs.

### Kawabe Adaptation: March 02, 2026
- **Goal:** Adapt sensible elements from Kawabe & Takano (2026) hierarchical agent framework.
- **Assessment:** Existing architecture already implements hierarchy (Orchestrator→Writer→Critic sub-checks) and feedback propagation (REVISE/FAIL routing). Full rewrite skipped.
- **Result:**
    - **Structured Feedback:** Added `CritiqueResult.to_revision_prompt()` — categorizes failure into hallucination/completeness/safety buckets for targeted Writer revision.
    - **Meta-Prompt Accumulation:** Added pitfall tracking (`utils.py`) — recurring failure patterns auto-accumulate across runs and are prepended to Writer prompts (MAML-style meta-learning).
    - **Tests:** 9/9 new tests pass. 7/7 existing tests pass.
- **Momentum:** 10/10. Ready for ablation runs with before/after comparison.

### Phase 2–4 Sprint: March 02, 2026 (Afternoon)
- **Goal:** Close remaining thesis gaps identified in project audit.
- **Result:**
    - **Critic Repetition:** `repetition_variant` now flows through `critique_explanation()` → `_llm_critique()`, applied to Critic's verification call.
    - **Bug Fix:** Pitfall JSON path now resolves relative to project root (not CWD).
    - **BLEU/ROUGE Scorer:** `scripts/metrics_scorer.py` — pure Python, zero deps. BLEU-1/2, ROUGE-1/2/L implemented and self-tested.
    - **Ablation Upgrade:** Reference annotations added per function; BLEU/ROUGE columns added to `ablation_summary.md` table.
    - **3D Visualization:** `scripts/visualize_codebalance.py` — isometric Canvas 3D scatter; generates `results/codebalance_3d.html` with no dependencies.
    - **Phase 2 Hint Enrichment:** `analysis/hint_enricher.py` — 13 pattern detectors (threading, async, JPA, SQL injection, eval, validation, Spring MVC). `Must-Cover Questions` injected into Writer prompt.
    - **Tests:** 16/16 still passing after all changes.
- **Scorecard Update:**
    | Module | Status | Notes |
    | :--- | :--- | :--- |
    | **Hint Enrichment** | ✅ 100% | 13 patterns, Must-Cover Questions wired into Writer |
    | **BLEU/ROUGE** | ✅ 100% | Pure Python scorer, integrated in ablation |
    | **3D Visualization** | ✅ 100% | Self-contained HTML, no plotly needed |
    | **Ablation Runner** | ✅ 100% | 4 arms, BLEU/ROUGE, reference annotations |
- **Momentum:** 10/10.

### Audit Day: March 04, 2026
- **Action:** Codebase Audit & Gap Analysis.
- **Result:** Functionality confirms completion of finalizer, codebase visuals, hint enrichment. Found missing representation in README and Blueprint.
- **Adjustment:** Created `audit_report.md` and synced documentation with actual repository capabilities.
- **Momentum:** 10/10. Ready for final stretch and demo.

- **Momentum:** 10/10. Tooling is now enterprise-ready.

### Web Dashboard Overhaul: March 10, 2026
- **Goal:** Launch a production-grade web dashboard (v0.2.0-web-preview).
- **Result:**
    - **Unified Layout:** Created `base.html` with persistent navigation, search, and shared modal.
    - **Interactive 3D Hero:** Replaced static hero with dynamic Plotly/d3.js 3D scatter plot.
    - **Risk Treemap:** Integrated d3.js treemap for module-level debt visualization with drilldown logic.
    - **Function List:** Sortable/filterable table with color-coded risk axes (Energy, Debt, Safety).
    - **Search:** Global autocomplete search with split-view explanation results.
    - **CLI Integration:** Added `--web` and `--format json|markdown` flags for better terminal-to-web transitions.
- **Momentum:** 10/10. Submission-ready.