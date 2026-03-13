import os
from github import Github, Auth

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

def _get_client():
    if not GITHUB_TOKEN:
        raise Exception("GITHUB_TOKEN not set in environment.")
    return Github(auth=Auth.Token(GITHUB_TOKEN))

def list_repos():
    g = _get_client()
    repos = g.get_user().get_repos(type='all')
    return "\n".join([f"{r.name} — {r.description or 'no description'}" for r in repos])

def get_repo_files(repo_name, path=""):
    g = _get_client()
    repo = g.get_user().get_repo(repo_name)
    contents = repo.get_contents(path)
    return "\n".join([f.path for f in contents])

def read_file(repo_name, filepath):
    g = _get_client()
    repo = g.get_user().get_repo(repo_name)
    content = repo.get_contents(filepath)
    return content.decoded_content.decode('utf-8')

def push_file(repo_name, filepath, content, message="Update from Hazel"):
    g = _get_client()
    repo = g.get_user().get_repo(repo_name)
    try:
        existing = repo.get_contents(filepath)
        repo.update_file(filepath, message, content, existing.sha)
        return f"Updated {filepath} in {repo_name}"
    except:
        repo.create_file(filepath, message, content)
        return f"Created {filepath} in {repo_name}"

def get_recent_commits(repo_name, count=5):
    g = _get_client()
    repo = g.get_user().get_repo(repo_name)
    commits = list(repo.get_commits()[:count])
    return "\n".join([f"{c.commit.message} — {c.commit.author.date}" for c in commits])
