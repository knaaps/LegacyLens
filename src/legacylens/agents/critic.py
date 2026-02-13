"""Critic Agent - Verifies explanations for accuracy.

The Critic uses temperature=0.0 for deterministic, factual checking.
It compares the explanation against the actual source code to catch
hallucinations or inaccuracies.
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
    model: str = "qwen2.5-coder:7b",
) -> CritiqueResult:
    """
    Verify an explanation against the source code.

    Args:
        code: The original source code
        explanation: The explanation to verify
        model: Ollama model to use (should be different from Writer)

    Returns:
        CritiqueResult with pass/fail, confidence, and issues
    """
    prompt = f"""You are a code review expert. Your job is to verify if an explanation accurately describes the code.

SOURCE CODE:
```
{code}
```

EXPLANATION TO VERIFY:
{explanation}

VERIFICATION TASK:
1. Check if every claim in the explanation is supported by the code
2. Look for hallucinations (claims not in the code)
3. Check for missing critical functionality
4. Rate your confidence in the explanation's accuracy (0-100)

Respond in this EXACT format:
PASSED: [yes/no]
CONFIDENCE: [0-100]
ISSUES: [comma-separated list of problems, or "none"]
SUGGESTIONS: [how to improve, or "none needed"]"""

    try:
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={"temperature": 0.0},
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
        if line.upper().startswith("PASSED:"):
            value = line.split(":", 1)[1].strip().lower()
            passed = value in ("yes", "true", "1")
        elif line.upper().startswith("CONFIDENCE:"):
            try:
                confidence = int(line.split(":", 1)[1].strip())
                confidence = max(0, min(100, confidence))
            except ValueError:
                confidence = 50
        elif line.upper().startswith("ISSUES:"):
            issues_text = line.split(":", 1)[1].strip()
            if issues_text.lower() != "none":
                issues = [i.strip() for i in issues_text.split(",") if i.strip()]
        elif line.upper().startswith("SUGGESTIONS:"):
            suggestions = line.split(":", 1)[1].strip()
            if suggestions.lower() == "none needed":
                suggestions = ""

    return CritiqueResult(
        passed=passed,
        confidence=confidence,
        issues=issues,
        suggestions=suggestions,
    )
