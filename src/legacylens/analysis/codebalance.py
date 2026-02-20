"""3D CodeBalance Scorer — Energy, Debt, and Safety.

Scores code health on three axes, each rated 0-10:

    Energy (0-10):  How computationally expensive is this code?
                    High loops/recursion = high energy score.
    
    Debt (0-10):    How hard is this code to maintain?
                    Long functions, deep nesting, many params = high debt.
    
    Safety (0-10):  Are there risky patterns?
                    SQL injection, eval(), no validation = high safety score.

0 = healthy/low risk, 10 = problematic/high risk.

All scoring is PURELY STATIC — we count patterns in source code.
No LLM calls are needed.
"""

import re
from dataclasses import dataclass, field

from legacylens.analysis.complexity import (
    count_lines,
    count_loops,
    count_nesting_depth,
    count_parameters,
    has_recursion,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CodeBalanceScore:
    """
    The 3D CodeBalance result for a single function.
    
    Each axis is 0-10 (0 = healthy, 10 = problematic).
    Think of it like a health checkup — lower is better.
    """
    
    energy: int        # Computational cost
    debt: int          # Maintainability burden
    safety: int        # Security/correctness risk
    details: dict = field(default_factory=dict)  # What triggered each score
    
    @property
    def total(self) -> int:
        """Sum of all three scores (0-30). Lower is healthier."""
        return self.energy + self.debt + self.safety
    
    @property
    def grade(self) -> str:
        """
        Letter grade based on total score.
        
        A (0-5):   Excellent — clean, efficient, safe
        B (6-10):  Good — minor issues
        C (11-15): Fair — needs attention
        D (16-20): Poor — significant issues
        F (21-30): Critical — needs immediate refactoring
        """
        t = self.total
        if t <= 5:
            return "A"
        elif t <= 10:
            return "B"
        elif t <= 15:
            return "C"
        elif t <= 20:
            return "D"
        else:
            return "F"
    
    def __str__(self) -> str:
        return (
            f"CodeBalance [{self.grade}] "
            f"Energy={self.energy}/10  Debt={self.debt}/10  Safety={self.safety}/10"
        )


# ---------------------------------------------------------------------------
# Safety patterns we look for
# ---------------------------------------------------------------------------

# Each pattern is (regex, description, points)
SAFETY_PATTERNS = [
    # SQL injection risks
    (r'["\']SELECT\s.*\+', "String-concatenated SQL query", 3),
    (r'["\']INSERT\s.*\+', "String-concatenated SQL INSERT", 3),
    (r'["\']DELETE\s.*\+', "String-concatenated SQL DELETE", 4),
    (r'["\']UPDATE\s.*\+', "String-concatenated SQL UPDATE", 3),
    
    # Dangerous function calls
    (r'\beval\s*\(', "Use of eval()", 4),
    (r'\bexec\s*\(', "Use of exec()", 4),
    (r'\b__import__\s*\(', "Dynamic import", 2),
    
    # Hardcoded secrets
    (r'(?i)(password|secret|api.?key)\s*=\s*["\']', "Hardcoded credential", 3),
    
    # Shell injection
    (r'\bos\.system\s*\(', "os.system() call", 3),
    (r'\bsubprocess\..*shell\s*=\s*True', "Shell=True in subprocess", 3),
    
    # Java-specific
    (r'\.executeQuery\s*\(\s*["\'].*\+', "Concatenated SQL executeQuery", 4),
    (r'Runtime\.getRuntime\(\)\.exec', "Runtime.exec() call", 3),
    
    # Catch-all exception swallowing
    (r'except\s*:', "Bare except (swallows all errors)", 2),
    (r'catch\s*\(\s*Exception\s', "Catching generic Exception", 1),
]


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _score_energy(code: str, function_name: str = "") -> tuple[int, dict]:
    """
    Score computational cost (0-10).
    
    What increases energy:
        - Loops (+1 each)
        - Nested loops (+3)
        - Recursion (+3)
        - High McCabe complexity (+1 per 5 points above 5)
    
    Args:
        code: Source code of the function
        function_name: Name for recursion detection
        
    Returns:
        (score, details_dict)
    """
    score = 0
    details = {}
    
    # Count loops
    loops = count_loops(code)
    if loops["total"] > 0:
        score += loops["total"]
        details["loops"] = f"{loops['total']} loop(s)"
    
    # Nested loops are expensive
    if loops["nested"]:
        score += 3
        details["nested_loops"] = "Nested loops detected"
    
    # Recursion
    if function_name and has_recursion(code, function_name):
        score += 3
        details["recursion"] = "Recursive function"
    
    # Cap at 10
    score = min(score, 10)
    return score, details


def _score_debt(code: str) -> tuple[int, dict]:
    """
    Score maintainability burden (0-10).
    
    What increases debt:
        - Long functions (>30 lines: +1, >60: +2, >100: +3)
        - Deep nesting (>3 levels: +1 per extra level)
        - Many parameters (>4: +1, >6: +2)
        - Low comment ratio (<10% comments in >20 lines: +1)
        - Tech-debt markers: TODO, FIXME, HACK, XXX (+1 each, cap +3)
        - Excessive coupling: >8 distinct method calls (+1, >12: +2)
        - Magic numbers in conditions (+1)
        - Multiple return points (>3: +1)
    
    Args:
        code: Source code of the function
        
    Returns:
        (score, details_dict)
    """
    score = 0
    details = {}
    
    # Function length
    line_info = count_lines(code)
    code_lines = line_info["code"]
    
    if code_lines > 100:
        score += 3
        details["length"] = f"{code_lines} lines (very long)"
    elif code_lines > 60:
        score += 2
        details["length"] = f"{code_lines} lines (long)"
    elif code_lines > 30:
        score += 1
        details["length"] = f"{code_lines} lines (moderate)"
    
    # Nesting depth
    depth = count_nesting_depth(code)
    if depth > 3:
        extra = depth - 3
        score += extra
        details["nesting"] = f"Depth {depth} (deep)"
    
    # Parameter count
    params = count_parameters(code)
    if params > 6:
        score += 2
        details["params"] = f"{params} parameters (too many)"
    elif params > 4:
        score += 1
        details["params"] = f"{params} parameters (many)"
    
    # Comment ratio (only check for longer functions)
    if code_lines > 20 and line_info["total"] > 0:
        comment_ratio = line_info["comment"] / line_info["total"]
        if comment_ratio < 0.1:
            score += 1
            details["comments"] = "Low comment ratio (<10%)"
    
    # ── New heuristics ──
    
    # Tech-debt markers
    debt_keywords = ["TODO", "FIXME", "HACK", "XXX", "BUG"]
    debt_hits = sum(1 for kw in debt_keywords if kw in code)
    if debt_hits:
        penalty = min(debt_hits, 3)
        score += penalty
        details["debt_markers"] = f"{debt_hits} debt marker(s)"
    
    # Excessive coupling (many distinct method calls → god-method smell)
    call_count = len(re.findall(r'\b\w+\s*\(', code))
    if call_count > 12:
        score += 2
        details["coupling"] = f"{call_count} method calls (god method)"
    elif call_count > 8:
        score += 1
        details["coupling"] = f"{call_count} method calls (high coupling)"
    
    # Multiple return points → harder to follow
    return_count = len(re.findall(r'\breturn\b', code))
    if return_count > 3:
        score += 1
        details["returns"] = f"{return_count} return points"
    
    # Magic numbers in conditions (numeric literal in if/for/while)
    magic = re.findall(r'(?:if|for|while)\s*\(.*\b\d{2,}\b', code)
    if magic:
        score += 1
        details["magic_numbers"] = f"{len(magic)} magic number(s) in conditions"
    
    # Cap at 10
    score = min(score, 10)
    return score, details


def _score_safety(code: str) -> tuple[int, dict]:
    """
    Score security and correctness risk (0-10).
    
    We scan the code for known risky patterns like:
        - SQL injection (string concatenation in queries)
        - eval() / exec() usage
        - Hardcoded credentials
        - Shell injection
        - Exception swallowing
        - Missing null checks on object parameters
        - Unvalidated user input (@RequestParam without @Valid)
        - Unsafe type casting
        - Resource leaks (streams/connections without try-with-resources)
    
    Args:
        code: Source code of the function
        
    Returns:
        (score, details_dict)
    """
    score = 0
    details = {}
    found_issues = []
    
    # ── Pattern-based detection ──
    for pattern, description, points in SAFETY_PATTERNS:
        if re.search(pattern, code):
            score += points
            found_issues.append(description)
    
    # ── Java-specific: missing null checks ──
    # If code dereferences method parameters without checking null
    has_object_params = bool(re.search(
        r'\b(String|Owner|Model|Page|Pageable|Object|List|Map)\s+\w+', code
    ))
    null_patterns = [
        r'\bnull\b',
        r'\bOptional\b',
        r'@NonNull',
        r'Objects\.requireNonNull',
        r'Assert\.notNull',
        r'Optional\.ofNullable',
        r'if\s*\(\s*\w+\s*[!=]=\s*null',
    ]
    has_null_check = any(re.search(p, code) for p in null_patterns)
    if has_object_params and not has_null_check:
        score += 1
        found_issues.append("No null guards on object parameters")
    
    # ── Unvalidated user input (Spring) ──
    has_user_input = bool(re.search(r'@RequestParam|@PathVariable|@RequestBody', code))
    validation_patterns = [
        r'@Valid\b',
        r'@Validated\b',
        r'@NotNull\b',
        r'@NotBlank\b',
        r'@Size\b',
        r'@Pattern\b',
        r'@Min\b',
        r'@Max\b',
        r'BindingResult',       # Spring form validation
        r'Errors\s+\w+',       # Spring Errors parameter
    ]
    has_validation = any(re.search(p, code) for p in validation_patterns)
    if has_user_input and not has_validation:
        score += 2
        found_issues.append("User input without validation annotations")
    
    # ── Unsafe type casting ──
    unsafe_casts = re.findall(r'\(\s*(String|Integer|Object)\s*\)\s*\w+', code)
    if unsafe_casts:
        score += 1
        found_issues.append(f"{len(unsafe_casts)} unsafe type cast(s)")
    
    # ── Resource leaks (new InputStream/Connection/Statement without try-with-resources) ──
    has_resource = bool(re.search(
        r'new\s+(FileInputStream|BufferedReader|Connection|Statement|PreparedStatement)', code
    ))
    has_try_with = bool(re.search(r'try\s*\(', code))
    if has_resource and not has_try_with:
        score += 2
        found_issues.append("Resource opened without try-with-resources")
    
    if found_issues:
        details["issues"] = found_issues
    
    # Cap at 10
    score = min(score, 10)
    return score, details


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def score_code(code: str, function_name: str = "") -> CodeBalanceScore:
    """
    Calculate the 3D CodeBalance score for a piece of code.
    
    This is the main entry point. Pass in source code and get back
    scores on three axes:
    
        Energy:  How expensive is this code to run?
        Debt:    How hard is this code to maintain?
        Safety:  Are there security or correctness risks?
    
    Each axis is scored 0-10 (lower is better).
    
    Args:
        code: Source code string (a single function/method)
        function_name: Name of the function (used for recursion check)
        
    Returns:
        CodeBalanceScore with energy, debt, safety scores and details
        
    Example:
        >>> result = score_code("def foo():\\n    eval(input())")
        >>> result.safety  # High due to eval()
        4
        >>> result.grade
        'B'
    """
    energy, energy_details = _score_energy(code, function_name)
    debt, debt_details = _score_debt(code)
    safety, safety_details = _score_safety(code)
    
    details = {
        "energy": energy_details,
        "debt": debt_details,
        "safety": safety_details,
    }
    
    return CodeBalanceScore(
        energy=energy,
        debt=debt,
        safety=safety,
        details=details,
    )
