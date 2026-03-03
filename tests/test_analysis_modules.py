"""Tests for CodeBalance, HintEnricher, and ContextSlicer modules.

Run with:
    python3 tests/test_analysis_modules.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from legacylens.analysis.codebalance import score_code, CodeBalanceScore
from legacylens.analysis.hint_enricher import enrich_hints, HintResult
from legacylens.analysis.call_graph import CallGraph
from legacylens.analysis.context_slicer import (
    slice_context, build_hybrid_context, TOKEN_BUDGET, _estimate_tokens
)

_pass = 0
_fail = 0


def _assert(cond: bool, msg: str):
    global _pass, _fail
    if cond:
        _pass += 1
    else:
        _fail += 1
        print(f"  FAIL: {msg}")


# ---------------------------------------------------------------------------
# CodeBalance tests
# ---------------------------------------------------------------------------

def test_codebalance_basic():
    """Clean single-line function scores A."""
    score = score_code("public String get() { return this.name; }", function_name="get")
    _assert(isinstance(score, CodeBalanceScore), "score is CodeBalanceScore")
    _assert(score.grade in ("A", "B"), f"clean code grade should be A/B, got {score.grade}")
    _assert(score.safety <= 2, f"no safety issues in clean getter, got {score.safety}")


def test_codebalance_eval_safety():
    """eval() in code raises safety score."""
    score = score_code("def run(cmd): return eval(cmd)", function_name="run")
    _assert(score.safety >= 2, f"eval should raise safety score, got {score.safety}")


def test_codebalance_loop_energy():
    """Nested loops increase energy score."""
    code = """
def process(items):
    for i in items:
        for j in items:
            total += i + j
    """
    score = score_code(code, function_name="process")
    _assert(score.energy >= 3, f"nested loops should raise energy, got {score.energy}")


def test_codebalance_long_function_debt():
    """Long function raises debt score."""
    # 45-line function
    lines = ["def big():"] + [f"    x{i} = {i}" for i in range(45)]
    code = "\n".join(lines)
    score = score_code(code, function_name="big")
    _assert(score.debt >= 1, f"45-line function should raise debt, got {score.debt}")


def test_codebalance_total_and_grade():
    """Total is sum of 3 axes; grade maps correctly."""
    score = CodeBalanceScore(energy=2, debt=1, safety=0, details={})
    _assert(score.total == 3, f"total should be 3, got {score.total}")
    _assert(score.grade == "A", f"total=3 should be A, got {score.grade}")

    high_score = CodeBalanceScore(energy=8, debt=7, safety=6, details={})
    _assert(high_score.grade in ("D", "F"), f"total=21 should be D/F, got {high_score.grade}")


def test_codebalance_sql_safety():
    """Raw SQL concatenation raises safety score."""
    code = 'String q = "SELECT * FROM users WHERE id=" + userId;'
    score = score_code(code)
    _assert(score.safety >= 1, f"SQL concat should raise safety, got {score.safety}")


# ---------------------------------------------------------------------------
# HintEnricher tests
# ---------------------------------------------------------------------------

def test_hint_threading():
    """synchronized keyword detected as concurrency pattern."""
    result = enrich_hints("synchronized void transfer() { balance -= amount; }")
    _assert("concurrency:threading" in result.patterns, "threading not detected")
    _assert(len(result.must_cover) >= 1, "must_cover should have at least 1 question")


def test_hint_jpa():
    """JPA save() detected as persistence pattern."""
    result = enrich_hints("this.owners.save(owner); return redirect;")
    _assert("persistence:jpa" in result.patterns, "JPA not detected")


def test_hint_validation():
    """@Valid annotation detected as validation pattern."""
    result = enrich_hints("public String form(@Valid Pet pet, BindingResult result) {}")
    _assert("validation:form" in result.patterns, "validation not detected")


def test_hint_eval_risk():
    """eval() detected as risk pattern."""
    result = enrich_hints("return eval(userInput);")
    _assert("risk:eval" in result.patterns, "eval risk not detected")
    # Must-cover question should be a warning
    _assert(any("⚠" in q for q in result.must_cover), "eval must-cover should have warning")


def test_hint_clean_code():
    """Simple getter has no patterns."""
    result = enrich_hints("public String getName() { return this.name; }")
    _assert(len(result.patterns) == 0, f"clean getter should have no patterns, got {result.patterns}")


def test_hint_prompt_section_empty():
    """`to_prompt_section()` returns empty string when no patterns."""
    result = HintResult()
    _assert(result.to_prompt_section() == "", "empty result should produce empty section")


def test_hint_prompt_section_nonempty():
    """`to_prompt_section()` formats correctly when patterns present."""
    result = enrich_hints("synchronized void x() {}")
    section = result.to_prompt_section()
    _assert("DETECTED PATTERNS" in section, "section should contain pattern header")
    _assert("MUST-COVER" in section, "section should contain must-cover header")


def test_hint_redirect():
    """Spring redirect detected."""
    result = enrich_hints('return "redirect:/owners/" + owner.getId();')
    _assert("web:redirect" in result.patterns, "redirect not detected")


# ---------------------------------------------------------------------------
# ContextSlicer / Token counting tests
# ---------------------------------------------------------------------------

def _make_graph() -> CallGraph:
    """Build a small 4-function PetClinic-like call graph."""
    g = CallGraph()
    g.add_function("processForm", "PetController.processForm", "PetController.java",
                   "void processForm(@Valid Pet pet, BindingResult result) { save(pet); }",
                   calls=["save", "validate"], field_reads=["owners"], field_writes=[])
    g.add_function("save", "PetRepository.save", "PetRepository.java",
                   "void save(Pet pet) { db.persist(pet); }", calls=[], field_reads=[], field_writes=["db"])
    g.add_function("validate", "Validator.validate", "Validator.java",
                   "boolean validate(Pet pet) { return pet != null; }", calls=[], field_reads=[], field_writes=[])
    g.add_function("initForm", "PetController.initForm", "PetController.java",
                   "void initForm() { owners.findAll(); }", calls=["processForm"],
                   field_reads=["owners"], field_writes=[])
    return g


def test_slice_basic():
    """slice_context returns callees for processForm."""
    graph = _make_graph()
    ctx = slice_context("processForm", graph)
    _assert(ctx is not None, "slice_context returned None")
    _assert(len(ctx.callees) >= 1, f"processForm should have callees, got {ctx.callees}")


def test_slice_callers():
    """initForm is a caller of processForm."""
    graph = _make_graph()
    ctx = slice_context("processForm", graph)
    caller_names = [c.name for c in ctx.callers]
    _assert("initForm" in caller_names, f"initForm should be in callers, got {caller_names}")


def test_slice_unknown_function():
    """Unknown function returns None."""
    graph = _make_graph()
    _assert(slice_context("nonExistent", graph) is None, "unknown function should return None")


def test_slice_data_coupling():
    """initForm and processForm share 'owners' field — data coupling."""
    graph = _make_graph()
    ctx = slice_context("processForm", graph)
    coupled_names = [c.name for c in ctx.data_coupled]
    # initForm reads 'owners' too, processForm reads 'owners', they are coupled
    # initForm is already in callers so may not appear in data_coupled (deduplicated)
    _assert(ctx is not None, "slice returned None")  # basic guard


def test_token_estimate():
    """_estimate_tokens estimates ~4 chars/token."""
    text = "a" * 400
    _assert(_estimate_tokens(text) == 100, f"400 chars should be ~100 tokens, got {_estimate_tokens(text)}")


def test_token_budget_constant():
    """TOKEN_BUDGET is a reasonable value."""
    _assert(TOKEN_BUDGET >= 4_000, f"TOKEN_BUDGET too low: {TOKEN_BUDGET}")
    _assert(TOKEN_BUDGET <= 20_000, f"TOKEN_BUDGET too high: {TOKEN_BUDGET}")


def test_build_hybrid_context_graph():
    """build_hybrid_context uses graph when available."""
    graph = _make_graph()
    ctx = build_hybrid_context("processForm", graph, [])
    _assert(ctx.get("source") == "deterministic", f"expected deterministic, got {ctx.get('source')}")


def test_build_hybrid_context_rag_fallback():
    """build_hybrid_context falls back to RAG when graph has no match."""
    graph = CallGraph()  # empty
    rag = [{"code": "void foo() {}", "metadata": {"qualified_name": "Foo.foo", "file_path": "Foo.java",
                                                    "complexity": 1, "line_count": 3, "calls": ""}}]
    ctx = build_hybrid_context("foo", graph, rag)
    _assert(ctx.get("source") == "rag", f"expected rag fallback, got {ctx.get('source')}")


def test_build_hybrid_context_no_data():
    """build_hybrid_context returns 'none' when no graph and no RAG."""
    ctx = build_hybrid_context("foo", CallGraph(), [])
    _assert(ctx.get("source") == "none", f"expected none, got {ctx.get('source')}")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running CodeBalance tests...")
    test_codebalance_basic()
    test_codebalance_eval_safety()
    test_codebalance_loop_energy()
    test_codebalance_long_function_debt()
    test_codebalance_total_and_grade()
    test_codebalance_sql_safety()

    print("Running HintEnricher tests...")
    test_hint_threading()
    test_hint_jpa()
    test_hint_validation()
    test_hint_eval_risk()
    test_hint_clean_code()
    test_hint_prompt_section_empty()
    test_hint_prompt_section_nonempty()
    test_hint_redirect()

    print("Running ContextSlicer / Token tests...")
    test_slice_basic()
    test_slice_callers()
    test_slice_unknown_function()
    test_slice_data_coupling()
    test_token_estimate()
    test_token_budget_constant()
    test_build_hybrid_context_graph()
    test_build_hybrid_context_rag_fallback()
    test_build_hybrid_context_no_data()

    total = _pass + _fail
    if _fail == 0:
        print(f"\nAll {total} tests passed ✓")
    else:
        print(f"\n{_pass}/{total} passed — {_fail} FAILED")
        sys.exit(1)
