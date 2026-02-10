"""Critic Agent - Verifies explanations for accuracy.

Uses temperature=0.0 and a compact structured prompt for fast verification.
"""

import ollama
from dataclasses import dataclass


@dataclass
class CritiqueResult:
    """Result of the Critic's verification."""

    passed: bool
    confidence: int  # 0-100
    issues: list[str]
    suggestions: str

    def __str__(self) -> str:
        status = "✓ PASSED" if self.passed else "✗ FAILED"
        return f"{status} (Confidence: {self.confidence}%)"


def critique_explanation(
    code: str,
    explanation: str,
    model: str = "deepseek-coder:6.7b",
) -> CritiqueResult:
    """
    Verify an explanation against the source code.

    Uses the SAME model as Writer to avoid a second model load.
    """
    prompt = f"""Verify if this explanation matches the code. Check for hallucinations.

CODE:
{code}

EXPLANATION:
{explanation}

Reply EXACTLY in this format (one line each):
PASSED: yes or no
CONFIDENCE: 0-100
ISSUES: list or none
SUGGESTIONS: text or none needed"""

    try:
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={
                "temperature": 0.0,
                "num_predict": 100,  # Structured output is short
            },
        )

        return _parse_critique_response(response["response"])
    except Exception as e:
        return CritiqueResult(
            passed=False,
            confidence=0,
            issues=[f"Critic error: {e}"],
            suggestions="Retry verification",
        )


def _parse_critique_response(response: str) -> CritiqueResult:
    """Parse the Critic's structured response."""
    lines = response.strip().split("\n")

    passed = False
    confidence = 50
    issues = []
    suggestions = ""

    for line in lines:
        line = line.strip()
        upper = line.upper()
        if upper.startswith("PASSED:"):
            value = line.split(":", 1)[1].strip().lower()
            passed = value in ("yes", "true", "1")
        elif upper.startswith("CONFIDENCE:"):
            try:
                confidence = int(line.split(":", 1)[1].strip())
                confidence = max(0, min(100, confidence))
            except ValueError:
                confidence = 50
        elif upper.startswith("ISSUES:"):
            issues_text = line.split(":", 1)[1].strip()
            if issues_text.lower() != "none":
                issues = [i.strip() for i in issues_text.split(",") if i.strip()]
        elif upper.startswith("SUGGESTIONS:"):
            suggestions = line.split(":", 1)[1].strip()
            if suggestions.lower() == "none needed":
                suggestions = ""

    return CritiqueResult(
        passed=passed,
        confidence=confidence,
        issues=issues,
        suggestions=suggestions,
    )
