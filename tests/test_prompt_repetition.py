"""Unit tests for the prompt repetition wrapper (Leviathan et al. 2025)."""

import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from legacylens.agents.utils import with_prompt_repetition


SYSTEM = "You are a code expert."
QUERY = "Explain this function."
FULL = f"{SYSTEM}\n\n{QUERY}"
CODE_SUFFIX = "\nOutput the regenerated code directly, no explanations or reasoning."


def test_simple_variant():
    result = with_prompt_repetition(SYSTEM, QUERY, variant="simple")
    assert result == f"{FULL}\n\n{FULL}"


def test_verbose_variant():
    result = with_prompt_repetition(SYSTEM, QUERY, variant="verbose")
    assert result == f"{FULL}\n\nLet me repeat that for clarity:\n{FULL}"


def test_x3_variant():
    result = with_prompt_repetition(SYSTEM, QUERY, variant="x3")
    expected = (
        f"{FULL}\n\nLet me repeat that:\n{FULL}"
        f"\n\nOne more time to ensure accuracy:\n{FULL}"
    )
    assert result == expected


def test_fallback_unknown_variant():
    result = with_prompt_repetition(SYSTEM, QUERY, variant="unknown")
    assert result == FULL, "Unknown variant should return unmodified prompt"


def test_for_code_gen_flag():
    result = with_prompt_repetition(SYSTEM, QUERY, variant="simple", for_code_gen=True)
    full_with_code = FULL + CODE_SUFFIX
    assert result == f"{full_with_code}\n\n{full_with_code}"


def test_for_code_gen_off_by_default():
    result = with_prompt_repetition(SYSTEM, QUERY, variant="simple")
    assert CODE_SUFFIX.strip() not in result


def test_x3_with_code_gen():
    result = with_prompt_repetition(SYSTEM, QUERY, variant="x3", for_code_gen=True)
    # Should contain the code-gen suffix in each copy
    assert result.count("no explanations or reasoning") == 3


if __name__ == "__main__":
    test_simple_variant()
    test_verbose_variant()
    test_x3_variant()
    test_fallback_unknown_variant()
    test_for_code_gen_flag()
    test_for_code_gen_off_by_default()
    test_x3_with_code_gen()
    print("All 7 tests passed ✓")
