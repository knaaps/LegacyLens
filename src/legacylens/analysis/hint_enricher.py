"""Hint Enricher — Phase 2 context enrichment.

Detects runtime patterns and risk signals in code that the Writer
should explicitly address in its explanation.

Patterns detected (language-agnostic regex heuristics):
    - Concurrency:  threading, synchronized, locks, async/await
    - Persistence:  SQL statements, JPA / Hibernate calls
    - Validation:   @Valid, null checks, assert, hasErrors
    - Risk flags:   eval/exec, raw SQL concatenation, swallowed exceptions

Each pattern adds a "must-cover question" to the Writer prompt,
pushing it toward more specific and complete explanations.
"""

import re
from dataclasses import dataclass, field


@dataclass
class HintResult:
    """Detected runtime patterns and the must-cover questions they imply."""

    patterns: list[str] = field(default_factory=list)
    must_cover: list[str] = field(default_factory=list)

    def to_prompt_section(self) -> str:
        """Format as a prompt section for the Writer."""
        if not self.patterns and not self.must_cover:
            return ""
        lines = []
        if self.patterns:
            lines.append("DETECTED PATTERNS:")
            for p in self.patterns:
                lines.append(f"  • {p}")
        if self.must_cover:
            lines.append("\nMUST-COVER QUESTIONS (address each in your explanation):")
            for q in self.must_cover:
                lines.append(f"  → {q}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Each entry: (label, regex, must-cover question)
_PATTERNS = [
    # ── Concurrency ─────────────────────────────────────────────────────────
    (
        "concurrency:threading",
        r"\b(Thread|Runnable|ExecutorService|ThreadPool|synchronized|ReentrantLock|AtomicInteger|volatile)\b",
        "How is thread safety handled? Are shared resources protected?",
    ),
    (
        "concurrency:async_java",
        r"\b(CompletableFuture|Future|@Async|Callable|ForkJoin)\b",
        "Is this method asynchronous? What triggers it and what receives the result?",
    ),
    (
        "concurrency:async_python",
        r"\b(async def|await |asyncio\.|aiohttp|ThreadPoolExecutor)\b",
        "Is this coroutine or async? What must the caller await?",
    ),
    # ── Persistence ──────────────────────────────────────────────────────────
    (
        "persistence:jpa",
        r"\b(\.save\(|\.findById|\.delete\(|EntityManager|@Transactional|@Repository|CrudRepository)\b",
        "What database operation is performed? Is it transactional?",
    ),
    (
        "persistence:raw_sql",
        r"(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE)\s",
        "What SQL query is executed? What data is read or mutated?",
    ),
    # ── Validation ───────────────────────────────────────────────────────────
    (
        "validation:form",
        r"\b(@Valid|BindingResult|hasErrors\(\)|rejectValue\(|@NotNull|@Size|@Min|@Max)\b",
        "What input validation is performed? What happens on failure?",
    ),
    (
        "validation:null_check",
        r"\b(Objects\.requireNonNull|== null|!= null|Optional\.of|\.orElse\(|\.orElseThrow)\b",
        "How are null or missing values handled?",
    ),
    # ── Risk / Security ──────────────────────────────────────────────────────
    (
        "risk:eval",
        r"\b(eval\(|exec\(|Runtime\.getRuntime|ProcessBuilder|ScriptEngine)\b",
        "⚠ Dangerous pattern detected — explain the security implications of eval/exec/shell execution.",
    ),
    (
        "risk:sql_injection",
        r'(\"SELECT|"INSERT|"UPDATE|"DELETE).*\+',
        "⚠ Possible SQL injection via string concatenation — note the risk in your explanation.",
    ),
    (
        "risk:swallowed_exception",
        r"catch\s*\(.*\)\s*\{\s*\}",
        "An empty catch block was detected — explain what error is being silently swallowed.",
    ),
    (
        "risk:hardcoded_creds",
        r'(password|secret|api_key|token)\s*=\s*["\']',
        "⚠ Possible hardcoded credential — mention this as a security concern.",
    ),
    # ── Spring MVC specifics ─────────────────────────────────────────────────
    (
        "web:redirect",
        r'\breturn\s+"redirect:',
        "What is the redirect target? Under what conditions is it triggered?",
    ),
    (
        "web:exception_handler",
        r"\b(@ExceptionHandler|throw new |throws )\b",
        "What exceptions are thrown or handled? How should callers respond?",
    ),
]


def enrich_hints(code: str) -> HintResult:
    """
    Detect runtime patterns in code and build must-cover questions.

    Args:
        code: Source code of the function to analyse

    Returns:
        HintResult with detected patterns and must-cover questions
    """
    result = HintResult()
    seen_questions: set[str] = set()

    for label, pattern, question in _PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            result.patterns.append(label)
            if question not in seen_questions:
                result.must_cover.append(question)
                seen_questions.add(question)

    return result
