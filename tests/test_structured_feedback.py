"""Unit tests for structured feedback + meta-prompt accumulation."""

import sys
import json
import tempfile
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from legacylens.agents.critic import CritiqueResult
from legacylens.agents.utils import (
    load_known_pitfalls,
    save_known_pitfalls,
    record_critique_pitfalls,
    build_pitfall_guidance,
)


# ── to_revision_prompt tests ─────────────────────────────────────────────

def test_revision_prompt_hallucination():
    cr = CritiqueResult(
        passed=False, confidence=40,
        issues=["Explanation references names not found in code: fakeMethod"],
        suggestions="Remove fakeMethod reference",
        factual_passed=False, completeness_pct=80,
    )
    text = cr.to_revision_prompt()
    assert "HALLUCINATION FIX" in text
    assert "fakeMethod" in text


def test_revision_prompt_completeness():
    cr = CritiqueResult(
        passed=False, confidence=60,
        issues=["Missing coverage: error handling, side effects"],
        suggestions="Add error details",
        factual_passed=True, completeness_pct=40,
    )
    text = cr.to_revision_prompt()
    assert "COMPLETENESS GAP" in text
    assert "40%" in text


def test_revision_prompt_safety():
    cr = CritiqueResult(
        passed=False, confidence=50,
        issues=["Unmentioned risk: SQL injection via string concat"],
        suggestions="Mention SQL risk",
        factual_passed=True, completeness_pct=80,
    )
    text = cr.to_revision_prompt()
    assert "SAFETY RISKS" in text
    assert "SQL" in text


def test_revision_prompt_clean():
    cr = CritiqueResult(
        passed=True, confidence=90,
        issues=[], suggestions="",
        factual_passed=True, completeness_pct=100,
    )
    text = cr.to_revision_prompt()
    assert "Minor quality issues" in text


# ── Pitfall accumulation tests ────────────────────────────────────────────

def test_pitfall_load_empty():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "pitfalls.json"
        data = load_known_pitfalls(p)
        assert data == {"hallucination": [], "completeness": [], "safety": []}


def test_pitfall_save_and_load():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "pitfalls.json"
        data = {"hallucination": ["fake caller"], "completeness": [], "safety": []}
        save_known_pitfalls(data, p)
        loaded = load_known_pitfalls(p)
        assert loaded["hallucination"] == ["fake caller"]


def test_pitfall_record_accumulates():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "pitfalls.json"
        cr = CritiqueResult(
            passed=False, confidence=40,
            issues=["Explanation references names not found in code: badRef"],
            suggestions="", factual_passed=False, completeness_pct=60,
        )
        # Record once — stored raw
        record_critique_pitfalls(cr, path=p)
        data = load_known_pitfalls(p)
        assert len(data["hallucination"]) == 1

        # Record again — now 2 occurrences
        record_critique_pitfalls(cr, path=p)
        data = load_known_pitfalls(p)
        assert len(data["hallucination"]) == 2

        # Guidance should surface it (threshold=2 met)
        guidance = build_pitfall_guidance(p, threshold=2)
        assert "badRef" in guidance


def test_build_guidance_empty():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "pitfalls.json"
        guidance = build_pitfall_guidance(p)
        assert guidance == ""


def test_build_guidance_with_data():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "pitfalls.json"
        # Need 2 occurrences to meet default threshold
        data = {
            "hallucination": ["invented caller processUser", "invented caller processUser"],
            "completeness": ["Missing coverage: error handling", "Missing coverage: error handling"],
            "safety": [],
        }
        save_known_pitfalls(data, p)
        guidance = build_pitfall_guidance(p)
        assert "AVOID" in guidance
        assert "processUser" in guidance
        assert "Ensure coverage" in guidance


if __name__ == "__main__":
    test_revision_prompt_hallucination()
    test_revision_prompt_completeness()
    test_revision_prompt_safety()
    test_revision_prompt_clean()
    test_pitfall_load_empty()
    test_pitfall_save_and_load()
    test_pitfall_record_accumulates()
    test_build_guidance_empty()
    test_build_guidance_with_data()
    print("All 9 tests passed ✓")
