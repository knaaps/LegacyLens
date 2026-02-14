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
| **CodeBalance** | ✅ 85% | 3D Scoring working. Missing visualization. |
| **Regeneration** | ✅ 100% | **Implemented via Tree-Sitter AST Similarity.** |
| **Hint Enrichment**| 🟡 50% | Compositional Critic handles risk/completeness. Runtime patterns next. |

### 🚀 Sprint Plan to Submission (Mar 17)

#### Week 7 (Feb 12-16): Critical Gap Fill
- [x] Implement **Regeneration Validation** (Phase 5) - *Thesis Critical*
- [x] Refactor Critic to **Compositional Mode** (Phase 3 novelty)
- [x] Add **LLM Provider Abstraction** (Groq support for speed)

#### Week 8 (Feb 17-23): Context & Polish
- [ ] Add **Finalizer Agent** (Phase 3 completion)
- [ ] Implement **Hint Enrichment** (Runtime patterns, "Must-Cover" questions)
- [ ] Add accurate **Token Counting**
- [ ] First full end-to-end test on Spring PetClinic

#### Week 9 (Feb 24 - Mar 2): Evaluation
- [ ] Build Test Corpus (50 functions)
- [ ] Script BLEU/ROUGE scoring
- [ ] Run Ablation Study (RAG vs Hybrid)

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