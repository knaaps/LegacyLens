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

def _flatten_ast(node) -> list[str]:
    """
    Flatten a tree-sitter AST into a list of node types.

    This captures the *structure* of the code (e.g., "if_statement",
    "for_statement", "method_invocation") while ignoring variable names,
    whitespace, and formatting differences.

    Example:
        "def add(a, b): return a + b"
        → ["function_definition", "parameters", "identifier", "identifier",
           "return_statement", "binary_operator", ...]
    """
    result = [node.type]
    for child in node.children:
        result.extend(_flatten_ast(child))
    return result


def compute_ast_similarity(original: str, regenerated: str, language: str) -> float:
    """
    Compare two code snippets by their AST structure.

    Uses a simple sequence-overlap approach:
    1. Parse both snippets into ASTs
    2. Flatten each AST into a list of node types
    3. Compute overlap ratio (intersection / union)

    Args:
        original:    The original source code
        regenerated: The LLM-regenerated code
        language:    "python" or "java"

    Returns:
        Similarity score between 0.0 and 1.0
    """
    parser = _get_parser(language)

    tree_a = parser.parse(original.encode("utf-8"))
    tree_b = parser.parse(regenerated.encode("utf-8"))

    nodes_a = _flatten_ast(tree_a.root_node)
    nodes_b = _flatten_ast(tree_b.root_node)

    if not nodes_a and not nodes_b:
        return 1.0  # Both empty — trivially identical
    if not nodes_a or not nodes_b:
        return 0.0  # One is empty

    # Sequence overlap: count how many node types appear in both lists
    # Using multiset intersection (order-insensitive but count-sensitive)
    from collections import Counter

    counts_a = Counter(nodes_a)
    counts_b = Counter(nodes_b)

    # Intersection: min of each type count
    intersection = sum((counts_a & counts_b).values())
    # Union: max of each type count
    union = sum((counts_a | counts_b).values())

    return intersection / union if union > 0 else 0.0


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
