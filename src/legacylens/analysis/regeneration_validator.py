"""Regeneration Validator — Verify explanations by regenerating code.

The idea is simple: if an explanation is good, an LLM should be able
to write the code back from it. We compare the original and regenerated
code using AST (tree-sitter) structural similarity instead of raw text.

Usage:
    result = validate_regeneration(original_code, explanation, language="java")
    print(result)  # {"fidelity": 0.82, "passed": True, "details": "..."}
"""

from legacylens.agents.provider import llm_generate
from legacylens.agents.utils import with_prompt_repetition

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

    By using only types (no depth), we remove sensitivity to outer wrappers
    (e.g. if the LLM wraps the generated method in a dummy class).
    """
    # Filter out noise nodes like comments, punctuation, and errors
    noise_types = {
        "comment", "line_comment", "block_comment", "ERROR",
        ";", "(", ")", "{", "}", ",", ".", "[", "]"
    }
    
    if node.type in noise_types:
        return []
        
    result = [node.type]
    for child in node.children:
        result.extend(_flatten_ast(child))
    return result


def _extract_method_node(root_node):
    if root_node.type == "program":
        for child in root_node.children:
            if child.type in ("class_declaration", "interface_declaration"):
                for body in child.children:
                    if body.type == "class_body":
                        for grand in body.children:
                            if grand.type in ("method_declaration", "constructor_declaration"):
                                return grand
            elif child.type in ("method_declaration", "function_definition"):
                return child
    # fallback for bare method or class root
    if root_node.type in ("class_declaration", "interface_declaration"):
        for child in root_node.children:
            if child.type == "class_body":
                for grand in child.children:
                    if grand.type in ("method_declaration", "constructor_declaration"):
                        return grand
    return root_node


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
    stripped = _re.sub(r"^(get|set)(?=[A-Z]\w{2,})", "", name)
    lower = stripped.lower()

    for group in _CALL_SYNONYMS:
        if lower in group:
            return sorted(group)[0]  # canonical = alphabetically first

    return stripped


def compute_ast_similarity(original: str, regenerated: str, language: str) -> float:
    """
    Compare two code snippets by their AST structure.

    Uses a weighted combination:
        60 %  — Structural similarity (SequenceMatcher on flat list of
                 node types, preserving ordering but ignoring depth)
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

    # Strip class wrappers before comparison (Khati KCH depth-offset fix)
    node_a = _extract_method_node(tree_a.root_node)
    node_b = _extract_method_node(tree_b.root_node)

    seq_a = _flatten_ast(node_a)
    seq_b = _flatten_ast(node_b)

    if not seq_a and not seq_b:
        return 1.0  # Both empty — trivially identical
    if not seq_a or not seq_b:
        return 0.0  # One is empty

    # Structural similarity — order-sensitive, depth-aware
    structural_sim = SequenceMatcher(None, seq_a, seq_b).ratio()

    # API-call overlap — order-insensitive, synonym-aware
    # Use the unwrapped method node so we score method-body calls only
    calls_a = {_normalize_call(c) for c in _extract_api_calls(node_a)}
    calls_b = {_normalize_call(c) for c in _extract_api_calls(node_b)}
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
    original_code: str = "",
    language: str = "java",
    model: str = "deepseek-coder:6.7b",
    repetition_variant: str | None = None,
) -> str:
    """
    Ask the LLM to regenerate code from an explanation.

    Uses a detailed prompt that requests an exact structural equivalent,
    preserving annotations, parameter types, return type, and control flow.

    When repetition_variant is set, applies Leviathan et al. (2025) prompt
    repetition to boost structural fidelity — the repeated prompt enables
    full token attention, improving recall of function calls, annotations,
    and control-flow patterns.

    Args:
        explanation:        The natural-language explanation of the code
        original_code:      The original source code (used for signature)
        language:           Target language ("java" or "python")
        model:              Model to use (auto-mapped for Groq)
        repetition_variant: Repetition strategy — None (off), "simple",
                            "verbose", or "x3"

    Returns:
        The regenerated code string
    """
    signature_lines = []
    for line in original_code.split('\n'):
        signature_lines.append(line)
        if '{' in line:
            break
    original_method_signature = '\n'.join(signature_lines)

    regen_prompt = f"""Regenerate the {language.capitalize()} method EXACTLY as shown below. 
Preserve signature, annotations, parameters, and body 100%:
{original_method_signature}

{explanation}"""

    system_prompt = (
        f"You are reconstructing the EXACT ORIGINAL {language} method from its explanation."
    )

    # Force 'simple' repetition to enable Leviathan et al. 2025
    prompt = with_prompt_repetition(
        system_prompt,
        regen_prompt,
        variant="simple",
        for_code_gen=True,
    )

    import os
    original_provider = os.environ.get("LLM_PROVIDER")
    os.environ["LLM_PROVIDER"] = "local"
    try:
        raw = llm_generate(
            prompt=prompt, 
            model="deepseek-coder:6.7b", 
            temperature=0.2
        )
        with open("debug_raw.txt", "w") as f:
            f.write(raw)
    finally:
        if original_provider is not None:
            os.environ["LLM_PROVIDER"] = original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)

    code = _extract_code_from_response(raw, language)
    with open("debug_ext.txt", "w") as f:
        f.write(code)
    return code.strip()
def _strip_class_wrapper(code: str) -> str:
    import re
    code = code.strip()
    if not code.endswith('}'):
        return code
    
    first_brace = code.find('{')
    if first_brace == -1:
        return code
        
    preamble = code[:first_brace].strip()
    # Check if the preamble defines a class wrapper
    if re.search(r'^(public\s+|private\s+|protected\s+)?(final\s+|abstract\s+)?class\s+\w+', preamble):
        inner = code[first_brace+1:-1].strip('\n')
        # Smart un-indent inner content
        lines = inner.split('\n')
        unindented = []
        for line in lines:
            if line.startswith('    '):
                unindented.append(line[4:])
            elif line.startswith('\t'):
                unindented.append(line[1:])
            else:
                unindented.append(line)
        return '\n'.join(unindented)
    return code


def _extract_code_from_response(raw: str, language: str) -> str:
    """Extract clean code from a potentially prose-contaminated LLM response.

    The regeneration LLM occasionally wraps its output in markdown, includes
    an explanatory preamble, or returns the explanation instead of code.
    We use a progressive extraction strategy:

    1. If the whole response looks like code (starts with annotation or keyword)
       → return as-is after stripping whitespace.
    2. If there are markdown code fences → extract the first fenced block.
    3. If there are Java/Python method signatures in the text → extract from
       the first one to the end (handles "Here is the code:\n@GetMapping...").
    4. Return whatever we found, or the raw stripped text as last resort.
    """
    import re

    text = raw.strip()

    # Stage 1: Whole response looks like raw code already
    code_starters = (
        "@",
        "public ",
        "private ",
        "protected ",
        "static ",
        "def ",
        "class ",
        "import ",
        "package ",
    )
    first_line = text.split("\n")[0].lstrip()
    if any(first_line.startswith(s) for s in code_starters):
        return _strip_class_wrapper(text)

    # Stage 2: Markdown code fence extraction  ```java ... ``` or ``` ... ```
    fence_pattern = re.compile(
        r"```(?:java|python|py|kotlin)?\s*\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    fences = fence_pattern.findall(text)
    if fences:
        # Prefer the largest block (most likely to be the full method)
        return _strip_class_wrapper(max(fences, key=len).strip())

    # Stage 3: Find first Java/Python code-like line and take everything from there
    # This handles "Here is the reconstructed method:\n@GetMapping..."
    if language == "java":
        code_start = re.search(
            r"^(@\w+|public |private |protected |static |void |[A-Z]\w+\s+\w+\s*\()",
            text,
            re.MULTILINE,
        )
    else:  # python
        code_start = re.search(
            r"^(def |class |@\w+|import |from )",
            text,
            re.MULTILINE,
        )

    if code_start:
        return _strip_class_wrapper(text[code_start.start() :].strip())

    # Stage 4: Last resort — return full text (will score low, that's informative)
    return _strip_class_wrapper(text)


# ---------------------------------------------------------------------------
# Public API — end-to-end validation
# ---------------------------------------------------------------------------


def validate_regeneration(
    original_code: str,
    explanation: str,
    language: str = "java",
    threshold: float = 0.65,
    model: str = "deepseek-coder:6.7b",
    repetition_variant: str | None = None,
) -> dict:
    """
    Validate an explanation by regenerating code and checking AST similarity.

    This is the main entry point. It:
    1. Asks the LLM to regenerate code from the explanation
    2. Parses both original and regenerated code into ASTs
    3. Computes structural similarity
    4. Returns pass/fail based on threshold

    Args:
        original_code:      The original source code
        explanation:         The explanation to validate
        language:            "java" or "python"
        threshold:           Minimum similarity to pass (default 0.65)
        model:               Model to use for regeneration
        repetition_variant:  Prompt repetition strategy (None, "simple",
                             "verbose", or "x3")

    Returns:
        Dict with keys: fidelity (float), passed (bool), details (str)
    """
    # Step 1: Regenerate
    regenerated = regenerate_code(
        explanation=explanation,
        original_code=original_code,
        language=language,
        model=model,
        repetition_variant=repetition_variant,
    )

    # Step 2: Compare ASTs
    with open("debug_regen.java", "w") as f:
        f.write(regenerated)
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
