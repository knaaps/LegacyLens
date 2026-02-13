"""Extended Complexity Metrics — Beyond McCabe.

Provides additional code metrics used by CodeBalance to assess
code health. All metrics are purely deterministic (no LLM needed).

Metrics:
    - Line counts (total, blank, comment, code)
    - Nesting depth (deepest if/for/while level)
    - Parameter count
    - Loop count and type
"""

import re


def count_lines(code: str) -> dict:
    """
    Break down a code snippet into line categories.
    
    Args:
        code: Source code string
        
    Returns:
        Dict with keys: total, blank, comment, code
        
    Example:
        >>> count_lines("x = 1\\n\\n# comment\\ny = 2")
        {'total': 4, 'blank': 1, 'comment': 1, 'code': 2}
    """
    lines = code.split("\n")
    total = len(lines)
    blank = 0
    comment = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank += 1
        elif stripped.startswith(("#", "//", "*", "/*")):
            comment += 1

    return {
        "total": total,
        "blank": blank,
        "comment": comment,
        "code": total - blank - comment,
    }


def count_nesting_depth(code: str) -> int:
    """
    Find the deepest nesting level in the code.
    
    Counts indentation levels as a proxy for nesting depth.
    Works for both Python (indentation-based) and Java/C-style
    (brace-based, but still typically indented).
    
    Args:
        code: Source code string
        
    Returns:
        Maximum nesting depth (0 = flat, 1 = one level, etc.)
        
    Example:
        >>> count_nesting_depth("if True:\\n    for x in y:\\n        pass")
        2
    """
    max_depth = 0

    for line in code.split("\n"):
        stripped = line.lstrip()
        if not stripped:
            continue

        # Count leading spaces and convert to depth
        # (assume 4-space or 2-space indentation)
        leading_spaces = len(line) - len(stripped)
        if leading_spaces > 0:
            # Try 4-space first, fall back to 2-space
            depth = leading_spaces // 4
            if depth == 0:
                depth = leading_spaces // 2
            max_depth = max(max_depth, depth)

    return max_depth


def count_parameters(code: str) -> int:
    """
    Count the number of parameters in a function signature.
    
    Works for both Python and Java-style function declarations.
    
    Args:
        code: Source code of a single function
        
    Returns:
        Number of parameters (0 if none or can't detect)
        
    Example:
        >>> count_parameters("def foo(a, b, c):\\n    pass")
        3
    """
    # Look for the first parenthesized group (function signature)
    match = re.search(r"\(([^)]*)\)", code)
    if not match:
        return 0

    params_text = match.group(1).strip()
    if not params_text:
        return 0

    # Split by comma, filter out 'self' and 'cls' (Python)
    params = [p.strip() for p in params_text.split(",")]
    params = [p for p in params if p and p not in ("self", "cls")]

    return len(params)


def count_loops(code: str) -> dict:
    """
    Count loops and their types in the code.
    
    Args:
        code: Source code string
        
    Returns:
        Dict with keys: total, for_loops, while_loops, nested
        
    Example:
        >>> count_loops("for x in y:\\n    for z in w:\\n        pass")
        {'total': 2, 'for_loops': 2, 'while_loops': 0, 'nested': True}
    """
    for_loops = len(re.findall(r"\bfor\s*[\s(]", code))
    while_loops = len(re.findall(r"\bwhile\s*[\s(]", code))
    total = for_loops + while_loops

    # Check for nested loops (a loop inside a loop)
    # Simple heuristic: if total > 1, likely nested
    nested = total > 1

    return {
        "total": total,
        "for_loops": for_loops,
        "while_loops": while_loops,
        "nested": nested,
    }


def has_recursion(code: str, function_name: str) -> bool:
    """
    Check if a function calls itself (direct recursion).
    
    Args:
        code: Source code of the function
        function_name: Name of the function to check
        
    Returns:
        True if the function appears to call itself
    """
    # Look for the function name followed by ( in the body
    # Skip the definition line itself
    lines = code.split("\n")
    body = "\n".join(lines[1:])  # Skip first line (definition)

    pattern = rf"\b{re.escape(function_name)}\s*\("
    return bool(re.search(pattern, body))
