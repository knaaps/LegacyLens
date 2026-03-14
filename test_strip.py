import re

def strip_wrapper(code: str) -> str:
    code = code.strip()
    if not code.endswith('}'):
        return code
    
    # Check if the preamble contains 'class ' without matching a string/comment (rough regex)
    # The safest way is to regex from start of string to first '{'
    first_brace = code.find('{')
    if first_brace == -1:
        return code
        
    preamble = code[:first_brace].strip()
    # If the preamble looks like a standard class or public class declaration
    if re.search(r'^(public\s+|private\s+|protected\s+)?(final\s+|abstract\s+)?class\s+\w+', preamble):
        # We strip the wrapper
        inner = code[first_brace+1:-1].strip('\n')
        # Un-indent inner block by 1 level if it's consistently indented
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

tests = [
    "public class Temp {\n    public void foo() {\n    }\n}",
    "@RequestMapping\npublic void foo() {\n}",
    "class MyClass {\n\tpublic void main() {\n\t}\n}"
]

for t in tests:
    print("---")
    print(strip_wrapper(t))
