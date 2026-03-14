import sys, pathlib, json
from legacylens.analysis.regeneration_validator import _extract_code_from_response

p = pathlib.Path('results/regen_trace_processFindForm.json')
trace = json.loads(p.read_text())
# Unfortunately trace doesn't store regenerated_code by default in iteration.
# Let's run _extract_code_from_response on the raw llm text if it existed, but we don't have it.
# How can we capture the exact AST generation?
