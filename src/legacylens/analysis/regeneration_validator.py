"""Regeneration Validator — Verify explanations by regenerating code.

The idea is simple: if an explanation is good, an LLM should be able
to write the code back from it. We compare the original and regenerated
code using AST (tree-sitter) structural similarity instead of raw text.

Usage:
    result = validate_regeneration(original_code, explanation, language="java")
    print(result)  # {"fidelity": 0.82, "passed": True, "details": "..."}
"""

from legacylens.agents.provider import llm_generate

# ---------------------------------------------------------------------------
# Tree-sitter parsers (lazy-loaded, reused across calls)
# ---------------------------------------------------------------------------

_parsers = {}


def _get_parser(language: str):
    """Get or create a tree-sitter parser for the given language."""
    if language not in _parsers:
        from tree_sitter import Language, Parser

        if language == "python":
            import tree_sitter_python as tspython
            _parsers["python"] = Parser(Language(tspython.language()))
        elif language == "java":
            import tree_sitter_java as tsjava
            _parsers["java"] = Parser(Language(tsjava.language()))
        else:
            raise ValueError(f"Unsupported language: {language}")

    return _parsers[language]


# ---------------------------------------------------------------------------
# AST similarity — compare tree structures, not text
# ---------------------------------------------------------------------------

def _flatten_ast(node, depth: int = 0) -> list[tuple[str, int]]:
    """
    Flatten a tree-sitter AST into a list of (node_type, depth) tuples.

    This captures the *structure* of the code (e.g., "if_statement",
    "for_statement", "method_invocation") while ignoring variable names,
    whitespace, and formatting differences.

    Including depth preserves nesting context that plain node-type lists lose.
    """
    result = [(node.type, depth)]
    for child in node.children:
        result.extend(_flatten_ast(child, depth + 1))
    return result


def _extract_api_calls(node) -> set[str]:
    """Extract method/function call names from an AST for call-overlap scoring."""
    calls: set[str] = set()

    def walk(n):
        if n.type in ("method_invocation", "call_expression", "call"):
            name_node = n.child_by_field_name("name") or n.child_by_field_name("function")
            if name_node:
                calls.add(name_node.text.decode("utf-8"))
        for child in n.children:
            walk(child)

    walk(node)
    return calls


# Groups of method names the LLM may substitute for each other
_CALL_SYNONYMS = {
    frozenset({"find", "get", "load", "search", "retrieve", "lookup"}),
    frozenset({"save", "persist", "insert", "create", "store"}),
    frozenset({"delete", "remove", "drop", "erase"}),
    frozenset({"update", "modify", "edit", "patch", "set"}),
}


def _normalize_call(name: str) -> str:
    """
    Collapse synonymous method names so API-call overlap is less strict.

    Rules:
        1. Strip get/set prefixes from accessors  (getName → Name)
        2. Map synonymous verbs to a canonical form (findById → find)
    """
    import re as _re

    # Strip get/set prefix if remainder is at least 3 chars
    stripped = _re.sub(r'^(get|set)(?=[A-Z]\w{2,})', '', name)
    lower = stripped.lower()

    for group in _CALL_SYNONYMS:
        if lower in group:
            return sorted(group)[0]  # canonical = alphabetically first

    return stripped


def compute_ast_similarity(original: str, regenerated: str, language: str) -> float:
    """
    Compare two code snippets by their AST structure.

    Uses a weighted combination:
        60 %  — Depth-aware sequence similarity (SequenceMatcher on
                 (node_type, depth) tuples, preserving ordering)
        40 %  — API call overlap (Jaccard on method-call names, so
                 the regeneration must call the same methods)

    Args:
        original:    The original source code
        regenerated: The LLM-regenerated code
        language:    "python" or "java"

    Returns:
        Similarity score between 0.0 and 1.0
    """
    from difflib import SequenceMatcher

    parser = _get_parser(language)

    tree_a = parser.parse(original.encode("utf-8"))
    tree_b = parser.parse(regenerated.encode("utf-8"))

    seq_a = _flatten_ast(tree_a.root_node)
    seq_b = _flatten_ast(tree_b.root_node)

    if not seq_a and not seq_b:
        return 1.0  # Both empty — trivially identical
    if not seq_a or not seq_b:
        return 0.0  # One is empty

    # Structural similarity — order-sensitive, depth-aware
    structural_sim = SequenceMatcher(None, seq_a, seq_b).ratio()

    # API-call overlap — order-insensitive, synonym-aware
    calls_a = {_normalize_call(c) for c in _extract_api_calls(tree_a.root_node)}
    calls_b = {_normalize_call(c) for c in _extract_api_calls(tree_b.root_node)}
    if calls_a or calls_b:
        api_sim = len(calls_a & calls_b) / len(calls_a | calls_b)
    else:
        api_sim = 1.0  # No calls in either → assume match

    # Weighted combination
    return 0.6 * structural_sim + 0.4 * api_sim


# ---------------------------------------------------------------------------
# Code regeneration — ask the LLM to write code from an explanation
# ---------------------------------------------------------------------------

def regenerate_code(
    explanation: str,
    language: str = "java",
    model: str = "deepseek-coder:6.7b",
) -> str:
    """
    Ask the LLM to regenerate code from an explanation.

    Uses a detailed prompt that requests an exact structural equivalent,
    preserving annotations, parameter types, return type, and control flow.

    Args:
        explanation: The natural-language explanation of the code
        language:    Target language ("java" or "python")
        model:       Model to use (auto-mapped for Groq)

    Returns:
        The regenerated code string
    """
    prompt = f"""You are reconstructing the EXACT ORIGINAL {language} method from its explanation.

EXPLANATION:
{explanation}

REQUIREMENTS:
- Write the EXACT EQUIVALENT {language} method that this explanation describes
- Preserve ALL annotations (e.g. @GetMapping, @RequestParam, @Override)
- Preserve EXACT parameter types and return type
- Preserve the EXACT control-flow structure (if/else branches, loops, returns)
- Preserve ALL method calls mentioned in the explanation
- Do NOT add any functionality not described in the explanation
- Do NOT omit any functionality that IS described
- Output ONLY the raw {language} code — no markdown fences, no explanations

CODE:"""

    raw = llm_generate(prompt=prompt, model=model, temperature=0.2)

    # Strip markdown code fences if the LLM wraps the output
    code = raw.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        # Remove first and last lines (the fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        code = "\n".join(lines)

    return code.strip()


# ---------------------------------------------------------------------------
# Public API — end-to-end validation
# ---------------------------------------------------------------------------

def validate_regeneration(
    original_code: str,
    explanation: str,
    language: str = "java",
    threshold: float = 0.65,
    model: str = "deepseek-coder:6.7b",
) -> dict:
    """
    Validate an explanation by regenerating code and checking AST similarity.

    This is the main entry point. It:
    1. Asks the LLM to regenerate code from the explanation
    2. Parses both original and regenerated code into ASTs
    3. Computes structural similarity
    4. Returns pass/fail based on threshold

    Args:
        original_code: The original source code
        explanation:   The explanation to validate
        language:      "java" or "python"
        threshold:     Minimum similarity to pass (default 0.70)
        model:         Model to use for regeneration

    Returns:
        Dict with keys: fidelity (float), passed (bool), details (str)
    """
    # Step 1: Regenerate
    regenerated = regenerate_code(
        explanation=explanation,
        language=language,
        model=model,
    )

    # Step 2: Compare ASTs
    fidelity = compute_ast_similarity(original_code, regenerated, language)

    # Step 3: Report
    passed = fidelity >= threshold
    status = "Pass" if passed else "Fail"

    return {
        "fidelity": round(fidelity, 3),
        "passed": passed,
        "regenerated_code": regenerated,
        "details": f"{status} — {fidelity:.1%} structural similarity (threshold: {threshold:.0%})",
    }
