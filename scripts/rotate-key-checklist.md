# HZL Security — If a Secret Leaks

Read this if:
- You accidentally committed an API key
- GitHub sent you a secret scanning alert
- You pushed a .env file
- You're not sure but want to be safe

---

## DO THIS IMMEDIATELY (in order)

### 1. Rotate the key (takes 5 minutes, do it now)

| Service | Where to rotate |
|---|---|
| Anthropic API | console.anthropic.com → API Keys → delete + create new |
| ElevenLabs | elevenlabs.io → Profile → API Keys → regenerate |
| Tavily | app.tavily.com → Settings → regenerate |
| Google OAuth | console.cloud.google.com → Credentials → delete + recreate |
| GitHub PAT | github.com → Settings → Developer settings → delete + create |
| Home Assistant | HA dashboard → Profile → Long-lived tokens → delete + create |

**The old key is compromised. Rotating it makes it dead.**

---

### 2. Remove it from git history

If you pushed the secret to a GitHub repo, it's in the history even after you delete the file.

```bash
# Install git-filter-repo (do this once)
pip install git-filter-repo

# Remove the specific file from ALL history
git filter-repo --path .env --invert-paths --force

# Force push (this rewrites history — communicate with collaborators)
git push origin --force --all
git push origin --force --tags
```

For specific strings (if the key was embedded in code, not a file):
```bash
git filter-repo --replace-text <(echo 'YOUR_OLD_API_KEY_HERE==>REDACTED') --force
```

---

### 3. Check if it was used

- Anthropic console: check usage/billing for unexpected spikes
- Google Cloud: check IAM audit logs
- ElevenLabs: check character usage in dashboard

---

### 4. Update your .env

Put the new key in your local `.env`. Never in code.

```bash
# Confirm .env is in .gitignore
grep ".env" .gitignore

# If not:
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
```

---

### 5. Install the pre-commit hook so this never happens again

```bash
bash scripts/setup-hooks.sh
```

---

## Prevention Checklist (do these now)

- [ ] Run `bash scripts/setup-hooks.sh` in every HZL repo
- [ ] Confirm `.env` is in `.gitignore` in every repo
- [ ] Never use `git add .` — always `git add <specific files>`
- [ ] Review staged files with `git diff --cached` before committing
- [ ] Enable GitHub secret scanning: Settings → Security → Secret scanning
- [ ] All API keys live in `.env` only, accessed via `os.environ` or `process.env`
