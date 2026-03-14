import sys
sys.path.insert(0, './src')
from legacylens.analysis.parser import extract_methods_from_file

res = extract_methods_from_file('src/petclinic/owner/OwnerController.java', 'java')
tgt = [n for n in res if n['name'] == 'OwnerController.processFindForm'][0]
print("ORIGINAL CODE:")
print(tgt['code'])
