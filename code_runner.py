import subprocess
import tempfile
import os

SUPPORTED = {
    'python': ('python3', '.py'),
    'bash': ('bash', '.sh'),
    'javascript': ('node', '.js'),
}

def run_code(code, language='python', timeout=15):
    lang = language.lower().strip()
    if lang not in SUPPORTED:
        return f"Unsupported language: {lang}. Supported: {', '.join(SUPPORTED.keys())}"
    
    interpreter, ext = SUPPORTED[lang]
    
    # Check interpreter exists
    check = subprocess.run(['which', interpreter], capture_output=True)
    if check.returncode != 0:
        return f"{interpreter} is not installed on this Pi."
    
    with tempfile.NamedTemporaryFile(suffix=ext, mode='w', delete=False) as f:
        f.write(code)
        tmp = f.name
    
    try:
        result = subprocess.run(
            [interpreter, tmp],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout.strip()
        errors = result.stderr.strip()
        
        if errors and not output:
            return f"Error:\n{errors}"
        elif errors:
            return f"Output:\n{output}\n\nWarnings:\n{errors}"
        return output or "Code ran successfully with no output."
    except subprocess.TimeoutExpired:
        return f"Code timed out after {timeout} seconds."
    except Exception as e:
        return f"Execution error: {e}"
    finally:
        os.unlink(tmp)
