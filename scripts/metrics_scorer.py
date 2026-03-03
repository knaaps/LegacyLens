"""BLEU and ROUGE scoring — pure Python, no external dependencies.

Implements:
    - BLEU-1, BLEU-2 (unigram + bigram precision with brevity penalty)
    - ROUGE-1, ROUGE-2 (unigram + bigram recall-based F1)
    - ROUGE-L (longest common subsequence F1)

Use these to compare LLM-generated explanations against reference
explanations for the ablation study metrics chapter.
"""

import re
from collections import Counter


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def _ngrams(tokens: list[str], n: int) -> list[tuple]:
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


# ---------------------------------------------------------------------------
# BLEU
# ---------------------------------------------------------------------------

def bleu_n(hypothesis: str, reference: str, n: int) -> float:
    """Compute BLEU-n precision (clipped) between hypothesis and reference."""
    hyp_tokens = _tokenize(hypothesis)
    ref_tokens = _tokenize(reference)

    if not hyp_tokens or not ref_tokens:
        return 0.0

    hyp_ngrams = _ngrams(hyp_tokens, n)
    ref_ngrams = _ngrams(ref_tokens, n)

    if not hyp_ngrams:
        return 0.0

    ref_counts = Counter(ref_ngrams)
    hyp_counts = Counter(hyp_ngrams)

    # Clipped count: min(hyp_count, ref_count)
    clipped = sum(min(count, ref_counts[gram]) for gram, count in hyp_counts.items())

    precision = clipped / len(hyp_ngrams)

    # Brevity penalty
    bp = 1.0 if len(hyp_tokens) >= len(ref_tokens) else (len(hyp_tokens) / len(ref_tokens))

    return bp * precision


def bleu(hypothesis: str, reference: str) -> dict[str, float]:
    """Compute BLEU-1 and BLEU-2 scores."""
    return {
        "bleu1": bleu_n(hypothesis, reference, 1),
        "bleu2": bleu_n(hypothesis, reference, 2),
    }


# ---------------------------------------------------------------------------
# ROUGE
# ---------------------------------------------------------------------------

def _rouge_n(hypothesis: str, reference: str, n: int) -> dict[str, float]:
    """ROUGE-n precision, recall, F1."""
    hyp = _ngrams(_tokenize(hypothesis), n)
    ref = _ngrams(_tokenize(reference), n)

    if not hyp or not ref:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    ref_counts = Counter(ref)
    hyp_counts = Counter(hyp)

    overlap = sum(min(count, ref_counts[gram]) for gram, count in hyp_counts.items())

    precision = overlap / len(hyp)
    recall = overlap / len(ref)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


def _lcs_length(a: list, b: list) -> int:
    """Compute LCS length with O(min(m,n)) space."""
    if len(a) < len(b):
        a, b = b, a  # b is the shorter one
    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if a[i-1] == b[j-1]:
                curr[j] = prev[j-1] + 1
            else:
                curr[j] = max(prev[j], curr[j-1])
        prev = curr
    return prev[n]


def _rouge_l(hypothesis: str, reference: str) -> dict[str, float]:
    """ROUGE-L F1 based on Longest Common Subsequence."""
    hyp = _tokenize(hypothesis)
    ref = _tokenize(reference)

    if not hyp or not ref:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    lcs = _lcs_length(hyp, ref)
    precision = lcs / len(hyp)
    recall = lcs / len(ref)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


def rouge(hypothesis: str, reference: str) -> dict[str, float]:
    """Compute ROUGE-1, ROUGE-2, ROUGE-L F1 scores."""
    r1 = _rouge_n(hypothesis, reference, 1)
    r2 = _rouge_n(hypothesis, reference, 2)
    rl = _rouge_l(hypothesis, reference)

    return {
        "rouge1": r1["f1"],
        "rouge2": r2["f1"],
        "rougeL": rl["f1"],
    }


def score_explanation(hypothesis: str, reference: str) -> dict[str, float]:
    """Compute all BLEU + ROUGE metrics between hypothesis and reference explanation."""
    b = bleu(hypothesis, reference)
    r = rouge(hypothesis, reference)
    return {**b, **r}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ref = "The processFindForm method searches for owners by last name and redirects to details if one match is found."
    hyp = "processFindForm searches owners by last name. If exactly one owner matches it redirects to their details page."
    hyp_bad = "This function does some stuff with data."

    good = score_explanation(hyp, ref)
    bad = score_explanation(hyp_bad, ref)

    print("Good explanation:")
    for k, v in good.items():
        print(f"  {k}: {v:.3f}")

    print("\nBad explanation:")
    for k, v in bad.items():
        print(f"  {k}: {v:.3f}")

    assert good["rouge1"] > bad["rouge1"], "ROUGE-1 should be higher for the good explanation"
    assert good["bleu1"] > bad["bleu1"], "BLEU-1 should be higher for the good explanation"
    print("\nAll assertions passed ✓")
