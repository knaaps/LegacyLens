"""Complexity Metrics - McCabe cyclomatic complexity calculation.

Provides a shared utility for computing cyclomatic complexity scores,
used by both the Java and Python parsers.
"""


def calculate_mccabe_complexity(code: str) -> int:
    """
    Calculate McCabe cyclomatic complexity from source code.

    Counts decision points (branches) to estimate complexity:
    - Starts at 1 (baseline)
    - +1 for each branching keyword

    Works for both Java and Python code.

    Args:
        code: Source code string

    Returns:
        Complexity score (1 = simple, 10+ = complex)
    """
    branch_keywords = [
        "if ",
        "if(",
        "else if",
        "elif ",
        "for ",
        "for(",
        "while ",
        "while(",
        "catch ",
        "catch(",
        "except ",
        "case ",
        "&&",
        "||",
        " and ",
        " or ",
        "? ",  # Ternary
    ]

    complexity = 1  # Baseline

    for line in code.split("\n"):
        stripped = line.strip()
        for keyword in branch_keywords:
            if keyword in stripped:
                complexity += 1
                break  # Count once per line

    return complexity


def complexity_label(score: int) -> str:
    """
    Human-readable label for a complexity score.

    Args:
        score: McCabe complexity score

    Returns:
        Label string (Low/Moderate/High/Very High)
    """
    if score <= 5:
        return "Low"
    elif score <= 10:
        return "Moderate"
    elif score <= 20:
        return "High"
    else:
        return "Very High"
