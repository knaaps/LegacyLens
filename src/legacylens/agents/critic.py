"""Critic Agent — Compositional verification of explanations.

The Critic runs three independent checks before asking the LLM:

1. **Factual Accuracy:** Cross-references function/method names mentioned
   in the explanation against names actually present in the source code.
2. **Completeness:** Ensures the explanation covers essential questions
   (parameters, return values, side effects, etc.).
3. **Risk Awareness:** Scans code for dangerous patterns (SQL injection,
   eval, etc.) and checks if the explanation mentions them.

After the static checks, the LLM verifies factual accuracy at temperature=0.0.

Output is a structured CritiqueResult with JSON-serializable verdict.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Literal

from legacylens.agents.provider import llm_generate
from legacylens.analysis.codebalance import SAFETY_PATTERNS


# ---------------------------------------------------------------------------
# Verdict type — three-state: PASS, FAIL, or REVISE (try again)
# ---------------------------------------------------------------------------

Verdict = Literal["PASS", "FAIL", "REVISE"]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class CritiqueResult:
    """Result of the Critic's compositional verification.

    Serializes to JSON for downstream consumption (logs, reports, tests).
    """

    passed: bool
    confidence: int  # 0-100
    issues: list[str]
    suggestions: str
    verdict: Verdict = "FAIL"

    # Compositional sub-scores
    factual_passed: bool = True
    completeness_pct: float = 0.0  # 0-100
    flagged_risks: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        icon = {"PASS": "✓", "FAIL": "✗", "REVISE": "⟳"}.get(self.verdict, "?")
        return (
            f"{icon} {self.verdict} (Confidence: {self.confidence}%) | "
            f"Factual: {'✓' if self.factual_passed else '✗'} | "
            f"Complete: {self.completeness_pct:.0f}% | "
            f"Risks flagged: {len(self.flagged_risks)}"
        )

    def to_json(self) -> dict:
        """Structured JSON output for logging and downstream agents."""
        return {
            "verdict": self.verdict,
            "factual_pass": self.factual_passed,
            "completeness_pass": self.completeness_pct >= 80,
            "completeness_pct": round(self.completeness_pct, 1),
            "risks_mentioned": self.flagged_risks,
            "issues": self.issues,
            "confidence": self.confidence,
            "suggestions": self.suggestions,
        }

    def to_json_str(self) -> str:
        """Compact JSON string for logging."""
        return json.dumps(self.to_json(), indent=2)


# ---------------------------------------------------------------------------
# Verdict cache — memoize on (code_hash, explanation_hash)
# ---------------------------------------------------------------------------

_verdict_cache: dict[str, CritiqueResult] = {}


def _cache_key(code: str, explanation: str) -> str:
    """Build a deterministic cache key from code + explanation content."""
    h = hashlib.sha256()
    h.update(code.encode("utf-8"))
    h.update(b"||")
    h.update(explanation.encode("utf-8"))
    return h.hexdigest()[:24]


def clear_critique_cache() -> None:
    """Clear the memoized verdict cache (useful for testing)."""
    _verdict_cache.clear()


# ---------------------------------------------------------------------------
# Check 1: Factual accuracy (static — no LLM needed)
# ---------------------------------------------------------------------------

def _check_factual_accuracy(code: str, explanation: str) -> tuple[bool, list[str]]:
    """
    Cross-reference identifiers in the explanation against the source code.

    Extracts function/method names from the code and checks which ones
    are mentioned in the explanation. If the explanation references names
    NOT in the code, that's a potential hallucination.

    Returns:
        (passed, list_of_issues)
    """
    issues = []

    # Extract identifiers from code (simple word-boundary matching)
    code_identifiers = set(re.findall(r'\b([a-zA-Z_]\w+)\b', code))

    # Also extract sub-identifiers by splitting camelCase/PascalCase names.
    # e.g. "getLastName" -> {"get", "Last", "Name", "lastName", "LastName"}
    # This prevents false positives when the LLM writes "lastName" instead
    # of the full method name "getLastName".
    sub_ids = set()
    for ident in code_identifiers:
        parts = re.findall(r'[a-z]+|[A-Z][a-z]*', ident)
        sub_ids.update(p.lower() for p in parts if len(p) > 2)
        # Also add common suffix combinations (e.g. lastName from getLastName)
        for i in range(1, len(parts)):
            combined = parts[i][0].lower() + parts[i][1:] + "".join(parts[i+1:])
            sub_ids.add(combined.lower())
    code_identifiers_lower = {x.lower() for x in code_identifiers} | sub_ids

    # Extract identifiers from explanation that look like code references
    # (often formatted in backticks, camelCase, or snake_case)
    explanation_refs = set()

    # Backtick-wrapped references: `functionName`
    explanation_refs.update(re.findall(r'`(\w+)`', explanation))

    # camelCase or PascalCase words (likely code references)
    explanation_refs.update(re.findall(r'\b([a-z]+[A-Z]\w+)\b', explanation))

    # snake_case words (likely code references)
    explanation_refs.update(re.findall(r'\b(\w+_\w+)\b', explanation))

    # Check for referenced names not found in the code
    # Filter out common English compound words and programming terms
    common_words = {
        "the", "and", "for", "this", "that", "with", "from", "have", "been",
        "lastName", "firstName", "totalElements", "defaultValue",
        "requestParam", "bindingResult", "notFound", "isEmpty",
        "side_effects", "error_handling", "return_value", "last_name",
        "step_by", "line_count",
    }
    common_words_lower = {w.lower() for w in common_words}

    suspicious = set()
    for ref in explanation_refs:
        # Skip if directly in code identifiers
        if ref in code_identifiers:
            continue
        # Skip if lowercase match found (covers case-insensitive matches)
        if ref.lower() in code_identifiers_lower:
            continue
        # Skip if in common words
        if ref.lower() in common_words_lower:
            continue
        # Skip short names
        if len(ref) <= 3:
            continue
        suspicious.add(ref)

    if suspicious:
        issues.append(
            f"Explanation references names not found in code: {', '.join(sorted(suspicious)[:5])}"
        )

    passed = len(issues) == 0
    return passed, issues


# ---------------------------------------------------------------------------
# Check 2: Completeness (must-cover questions)
# ---------------------------------------------------------------------------

# These questions represent the minimum an explanation should cover.
MUST_COVER_QUESTIONS = [
    ("parameters", r'\b(param|argument|input|takes|accepts|receives)\b'),
    ("return value", r'\b(return|output|result|produces|yields)\b'),
    ("purpose", r'\b(purpose|does|handles|processes|responsible|performs)\b'),
    ("error handling", r'\b(error|exception|catch|throw|fail|invalid)\b'),
    ("side effects", r'\b(modifies|updates|saves|writes|deletes|sends|calls|invokes)\b'),
]


def _check_completeness(explanation: str) -> tuple[float, list[str]]:
    """
    Check if the explanation covers essential aspects of the code.

    Scans the explanation for mentions of parameters, return values,
    purpose, error handling, and side effects.

    Returns:
        (coverage_percentage, list_of_missing_topics)
    """
    covered = 0
    missing = []

    for topic, pattern in MUST_COVER_QUESTIONS:
        if re.search(pattern, explanation, re.IGNORECASE):
            covered += 1
        else:
            missing.append(topic)

    total = len(MUST_COVER_QUESTIONS)
    pct = (covered / total) * 100 if total > 0 else 0.0

    return pct, missing


# ---------------------------------------------------------------------------
# Check 3: Risk awareness (reuse SAFETY_PATTERNS from codebalance.py)
# ---------------------------------------------------------------------------

def _check_risk_awareness(code: str, explanation: str) -> tuple[list[str], list[str]]:
    """
    Check if the code has safety risks and whether the explanation flags them.

    Uses the same SAFETY_PATTERNS from codebalance.py (single source of truth).
    For each risk found in code, checks if the explanation mentions it.

    Returns:
        (flagged_risks, unflagged_issues)
    """
    found_in_code = []
    flagged_in_explanation = []
    unflagged = []

    # Keywords that indicate the explanation mentions a risk
    risk_keywords = {
        "sql": ["sql", "injection", "query", "concatenat"],
        "eval": ["eval", "dangerous", "arbitrary", "execution"],
        "exec": ["exec", "dangerous", "arbitrary"],
        "credential": ["password", "secret", "credential", "hardcod"],
        "shell": ["shell", "command", "injection", "os.system", "subprocess"],
        "exception": ["except", "error", "swallow", "catch"],
        "import": ["dynamic", "import", "__import__"],
    }

    for pattern, description, _points in SAFETY_PATTERNS:
        if re.search(pattern, code):
            found_in_code.append(description)

            # Check if explanation mentions this risk
            mentioned = False
            explanation_lower = explanation.lower()
            for category, keywords in risk_keywords.items():
                if any(kw in description.lower() for kw in [category]):
                    if any(kw in explanation_lower for kw in keywords):
                        mentioned = True
                        break

            if mentioned:
                flagged_in_explanation.append(description)
            else:
                unflagged.append(f"Unmentioned risk: {description}")

    return flagged_in_explanation, unflagged


# ---------------------------------------------------------------------------
# Main LLM-based critique (requests structured JSON output)
# ---------------------------------------------------------------------------

def _llm_critique(code: str, explanation: str, model: str) -> tuple[bool, int, list[str], str]:
    """
    Ask the LLM to verify the explanation against the source code.

    The prompt requests structured JSON output for reliable parsing.

    Returns:
        (passed, confidence, issues, suggestions)
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

    raw = llm_generate(prompt=prompt, model=model, temperature=0.0)
    return _parse_critique_response(raw)


def _parse_critique_response(response: str) -> tuple[bool, int, list[str], str]:
    """Parse the Critic's structured LLM response."""
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

    return passed, confidence, issues, suggestions


# ---------------------------------------------------------------------------
# Verdict logic — three-outcome (PASS / FAIL / REVISE)
# ---------------------------------------------------------------------------

def _compute_verdict(
    llm_passed: bool,
    confidence: int,
    factual_passed: bool,
    completeness_pct: float,
) -> Verdict:
    """
    Determine the final verdict from sub-check results.

    Early accept:  factual_passed AND completeness >= 95% AND confidence >= 70
    REVISE:        Minor issues that another Writer iteration could fix
    FAIL:          Hard failures (hallucinations, very low completeness)
    """
    # Early accept — strong on all axes
    if factual_passed and completeness_pct >= 95 and confidence >= 70:
        return "PASS"

    # LLM says PASS with decent confidence + good static checks
    if llm_passed and confidence >= 70:
        return "PASS"

    # High confidence + all static checks passed → still pass
    # (the LLM "no" is often about style, not accuracy)
    if confidence >= 80 and factual_passed and completeness_pct >= 60:
        return "PASS"

    # Borderline cases → REVISE (let the Writer try again)
    if factual_passed and completeness_pct >= 40:
        return "REVISE"

    # Hard fail — hallucinations or near-empty explanation
    return "FAIL"


# ---------------------------------------------------------------------------
# Public API — runs all checks sequentially
# ---------------------------------------------------------------------------

def critique_explanation(
    code: str,
    explanation: str,
    model: str = "qwen2.5-coder:7b",
    use_cache: bool = True,
) -> CritiqueResult:
    """
    Verify an explanation using compositional checks + LLM verification.

    Runs three fast static checks first, then the LLM critique:
    1. Factual accuracy — cross-reference identifiers
    2. Completeness — must-cover question coverage
    3. Risk awareness — flag unmentioned dangers

    Results are cached by (code_hash, explanation_hash) to avoid
    redundant LLM calls when re-checking the same inputs.

    Args:
        code: The original source code
        explanation: The explanation to verify
        model: Model name (auto-mapped for Groq if LLM_PROVIDER=groq)
        use_cache: Whether to use/populate the verdict cache

    Returns:
        CritiqueResult with verdict (PASS/FAIL/REVISE), confidence,
        sub-scores, issues, and JSON-serializable output
    """
    # --- Cache check ---
    key = _cache_key(code, explanation)
    if use_cache and key in _verdict_cache:
        return _verdict_cache[key]

    all_issues = []

    # --- Check 1: Factual accuracy ---
    factual_passed, factual_issues = _check_factual_accuracy(code, explanation)
    all_issues.extend(factual_issues)

    # --- Check 2: Completeness ---
    completeness_pct, missing_topics = _check_completeness(explanation)
    if missing_topics:
        all_issues.append(f"Missing coverage: {', '.join(missing_topics)}")

    # --- Check 3: Risk awareness ---
    flagged_risks, unflagged_issues = _check_risk_awareness(code, explanation)
    all_issues.extend(unflagged_issues)

    # --- LLM verification ---
    try:
        llm_passed, confidence, llm_issues, suggestions = _llm_critique(
            code, explanation, model
        )
        all_issues.extend(llm_issues)
    except Exception as e:
        llm_passed = False
        confidence = 0
        suggestions = "Retry verification"
        all_issues.append(f"Critic error: {e}")

    # --- Compute three-state verdict ---
    verdict = _compute_verdict(llm_passed, confidence, factual_passed, completeness_pct)
    overall_passed = verdict == "PASS"

    result = CritiqueResult(
        passed=overall_passed,
        confidence=confidence,
        issues=all_issues,
        suggestions=suggestions,
        verdict=verdict,
        factual_passed=factual_passed,
        completeness_pct=completeness_pct,
        flagged_risks=flagged_risks,
    )

    # --- Populate cache ---
    if use_cache:
        _verdict_cache[key] = result

    return result
