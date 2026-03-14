import json, sys
data = json.load(open('results/regen_trace_processFindForm.json'))
print(data['iterations'][0].keys())
print(data['iterations'][0]['regeneration_response'][:200])
