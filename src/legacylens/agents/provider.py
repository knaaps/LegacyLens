"""LLM Provider Factory — Toggle between Groq (cloud) and Ollama (local).

Usage:
    from legacylens.agents.provider import llm_generate

    # Uses LLM_PROVIDER env var to pick backend ("groq" or "local")
    response = llm_generate(prompt="Explain this code", model="default", temperature=0.3)

Set LLM_PROVIDER=groq and ensure apikey.env exists with your Groq key.
Default is "local" (Ollama).
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Provider backends
# ---------------------------------------------------------------------------

def _call_ollama(model: str, prompt: str, temperature: float) -> str:
    """Call the local Ollama server."""
    import ollama

    response = ollama.generate(
        model=model,
        prompt=prompt,
        options={"temperature": temperature},
    )
    return response["response"].strip()


def _call_groq(model: str, prompt: str, temperature: float) -> str:
    """Call the Groq cloud API."""
    from groq import Groq

    # Load API key from apikey.env if not already in environment
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        api_key = _load_api_key()

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    text = response.choices[0].message.content.strip()

    # Strip Qwen3's chain-of-thought <think>...</think> tags.
    # These contain internal reasoning that should not appear in output.
    import re
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    return text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Model mapping: local Ollama names → Groq-supported equivalents
# Qwen3-32B is specialized for code understanding and structured output,
# producing better explanations and more reliable verification than
# general-purpose models like Llama-3.3-70b.
GROQ_MODEL_MAP = {
    "deepseek-coder:6.7b": "qwen/qwen3-32b",       # Writer
    "qwen2.5-coder:7b": "qwen/qwen3-32b",           # Critic
    "qwen2.5-coder:7b-instruct": "qwen/qwen3-32b",  # Critic (instruct variant)
    "phi4-mini": "llama-3.3-70b-versatile",          # Fast strict checking
}


def _load_api_key() -> str:
    """Read the Groq API key from apikey.env in the project root."""
    # Walk up from this file to find apikey.env
    search_dirs = [
        Path.cwd(),
        Path(__file__).resolve().parent.parent.parent.parent,  # project root
    ]

    for d in search_dirs:
        env_file = d / "apikey.env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Accepts: groq="gsk_..." or GROQ_API_KEY=gsk_...
                    key, _, value = line.partition("=")
                    value = value.strip().strip("\"'")
                    if value.startswith("gsk_"):
                        return value

    raise RuntimeError(
        "Groq API key not found. "
        "Create apikey.env with: groq=\"gsk_your_key_here\""
    )


def _resolve_model(model: str, provider: str) -> str:
    """Map local model names to Groq equivalents when needed."""
    if provider == "groq":
        return GROQ_MODEL_MAP.get(model, model)
    return model


# ---------------------------------------------------------------------------
# Public API — this is the only function other modules need
# ---------------------------------------------------------------------------

def llm_generate(
    prompt: str,
    model: str = "deepseek-coder:6.7b",
    temperature: float = 0.3,
) -> str:
    """
    Generate text from an LLM, using whichever backend is configured.

    The backend is chosen by the LLM_PROVIDER env var:
        "groq"  → Groq cloud API (fast, needs API key)
        "local" → Ollama local server (private, slower)

    Args:
        prompt:      The prompt to send
        model:       Model name (auto-mapped for Groq)
        temperature: Sampling temperature (0.0 = deterministic)

    Returns:
        The model's text response, stripped of whitespace.
    """
    provider = os.environ.get("LLM_PROVIDER", "local").lower()
    resolved_model = _resolve_model(model, provider)

    if provider == "groq":
        return _call_groq(resolved_model, prompt, temperature)
    else:
        return _call_ollama(resolved_model, prompt, temperature)
