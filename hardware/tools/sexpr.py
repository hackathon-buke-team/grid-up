"""Small KiCad S-expression reader; preserves quoted strings on serialization."""
import re, json
class Q(str): pass
def parse(text):
    stack=[]; root=None
    for t in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text):
        if t=='(':
            n=[]
            if stack: stack[-1].append(n)
            else: root=n
            stack.append(n)
        elif t==')': stack.pop()
        else: stack[-1].append(Q(json.loads(t)) if t.startswith('"') else t)
    return root
def dump(x):
    if isinstance(x,list): return '('+' '.join(dump(y) for y in x)+')'
    if isinstance(x,Q): return json.dumps(str(x),ensure_ascii=False)
    return str(x)
def find(x,key): return next((y for y in x if isinstance(y,list) and y and y[0]==key),None)
def allof(x,key): return [y for y in x if isinstance(y,list) and y and y[0]==key]
