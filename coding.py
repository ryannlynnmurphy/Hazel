import os
import json
from code_runner import run_code

_HZL_DIR = os.path.dirname(os.path.abspath(__file__))
SNIPPETS_FILE = os.path.join(_HZL_DIR, "snippets.json")

def _load_snippets():
    if not os.path.exists(SNIPPETS_FILE):
        return []
    return json.load(open(SNIPPETS_FILE))

def _save_snippets(snippets):
    json.dump(snippets, open(SNIPPETS_FILE, 'w'), indent=2)

def save_snippet(name, code, language='python', description=''):
    snippets = _load_snippets()
    # Update if exists
    for s in snippets:
        if s['name'].lower() == name.lower():
            s.update({'code': code, 'language': language, 'description': description})
            _save_snippets(snippets)
            return f"Updated snippet: {name}"
    snippets.append({'name': name, 'code': code, 'language': language, 'description': description})
    _save_snippets(snippets)
    return f"Saved snippet: {name}"

def get_snippet(name):
    for s in _load_snippets():
        if s['name'].lower() == name.lower():
            return s
    return None

def list_snippets():
    snippets = _load_snippets()
    if not snippets:
        return "No snippets saved."
    return "\n".join([f"{s['name']} ({s['language']}) — {s.get('description','')}" for s in snippets])

def delete_snippet(name):
    snippets = [s for s in _load_snippets() if s['name'].lower() != name.lower()]
    _save_snippets(snippets)
    return f"Deleted snippet: {name}"

def execute_snippet(name):
    s = get_snippet(name)
    if not s:
        return f"No snippet found named '{name}'"
    return run_code(s['code'], s['language'])

def debug_code(code, error, language='python'):
    """Returns a prompt string for brain.py to pass to Claude"""
    return f"Debug this {language} code:\n```{language}\n{code}\n```\nError: {error}\nExplain the bug and provide the fix."
