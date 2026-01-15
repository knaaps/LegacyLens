"""Code explanation generator using Ollama."""

import ollama


def generate_explanation(
    code: str,
    query: str,
    metadata: dict,
    model: str = "deepseek-coder:6.7b",
) -> str:
    """
    Generate a natural language explanation of code using Ollama.
    
    Args:
        code: The source code to explain
        query: The user's question
        metadata: Static analysis facts (complexity, calls, etc.)
        model: Ollama model to use
        
    Returns:
        Generated explanation text
    """
    # Build context from metadata
    facts = []
    if metadata.get("complexity"):
        facts.append(f"Complexity score: {metadata['complexity']}")
    if metadata.get("line_count"):
        facts.append(f"Lines of code: {metadata['line_count']}")
    if metadata.get("calls"):
        calls = metadata["calls"]
        if isinstance(calls, str):
            calls = calls.split(",") if calls else []
        if calls:
            facts.append(f"Calls these functions: {', '.join(calls)}")
    
    facts_text = "\n".join(f"- {f}" for f in facts) if facts else "None available"
    
    prompt = f"""You are an expert developer explaining legacy code to a colleague.

CODE:
```
{code}
```

STATIC ANALYSIS FACTS:
{facts_text}

QUESTION: {query}

Provide a clear, concise explanation. Reference the static analysis facts where relevant."""

    try:
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={"temperature": 0.3},
        )
        return response["response"]
    except Exception as e:
        return f"[Error generating explanation: {e}]\n\nRetrieved code shown above."
