#!/bin/bash
# HZL Security — Pre-commit Hook Installer
# Run once per repo: bash scripts/setup-hooks.sh
# Blocks API keys, tokens, and passwords from ever hitting GitHub.

set -e

HOOK_DIR=".git/hooks"
HOOK_FILE="$HOOK_DIR/pre-commit"

if [ ! -d "$HOOK_DIR" ]; then
  echo "❌ Not a git repo. Run from your project root."
  exit 1
fi

cat > "$HOOK_FILE" << 'HOOK'
#!/bin/bash
# HZL Pre-commit Security Hook
# Scans staged files for secrets before every commit.

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "🔒 HZL Security: scanning for secrets..."

STAGED=$(git diff --cached --name-only --diff-filter=ACM)

if [ -z "$STAGED" ]; then
  exit 0
fi

# Patterns that should NEVER be committed
SECRET_PATTERNS=(
  "sk-ant-[a-zA-Z0-9\-]+"           # Anthropic API keys
  "AKIA[0-9A-Z]{16}"                 # AWS access keys
  "AIza[0-9A-Za-z\-_]{35}"          # Google API keys
  "ya29\.[0-9A-Za-z\-_]+"           # Google OAuth tokens
  "xoxb-[0-9]{11}-[0-9A-Za-z]+"     # Slack bot tokens
  "ghp_[a-zA-Z0-9]{36}"             # GitHub PATs
  "password\s*=\s*['\"][^'\"]{4,}"  # Hardcoded passwords
  "secret\s*=\s*['\"][^'\"]{4,}"    # Hardcoded secrets
  "private_key\s*=\s*['\"]"         # Private keys
  "-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----"  # PEM private keys
  "ELEVEN_LABS_API_KEY\s*=\s*[a-zA-Z0-9]+"  # ElevenLabs (Hazel)
  "CLAUDE_API_KEY\s*=\s*[a-zA-Z0-9]+"
  "ANTHROPIC_API_KEY\s*=\s*[a-zA-Z0-9]+"
  "TAVILY_API_KEY\s*=\s*[a-zA-Z0-9]+"
)

FOUND=0

for FILE in $STAGED; do
  # Skip binary files and .env.example
  if [[ "$FILE" == *".env.example"* ]]; then
    continue
  fi

  if git show ":$FILE" > /dev/null 2>&1; then
    CONTENT=$(git show ":$FILE" 2>/dev/null || echo "")

    for PATTERN in "${SECRET_PATTERNS[@]}"; do
      if echo "$CONTENT" | grep -qE "$PATTERN" 2>/dev/null; then
        echo -e "${RED}❌ SECRET DETECTED in $FILE${NC}"
        echo -e "${YELLOW}   Pattern matched: $PATTERN${NC}"
        FOUND=1
      fi
    done
  fi
done

if [ $FOUND -eq 1 ]; then
  echo ""
  echo -e "${RED}🚨 COMMIT BLOCKED — secrets found in staged files.${NC}"
  echo ""
  echo "Fix it:"
  echo "  1. Move secrets to .env (never commit .env)"
  echo "  2. Use process.env.VAR_NAME or os.environ['VAR_NAME']"
  echo "  3. If already pushed: rotate the key IMMEDIATELY"
  echo "  4. See: scripts/rotate-key-checklist.md"
  echo ""
  exit 1
fi

echo -e "${GREEN}✅ No secrets detected. Proceeding.${NC}"
exit 0
HOOK

chmod +x "$HOOK_FILE"

echo ""
echo "✅ Pre-commit hook installed at $HOOK_FILE"
echo "   Every commit will now be scanned for secrets."
echo ""
echo "Next: add your real .env to .gitignore:"
echo "  echo '.env' >> .gitignore"
echo "  echo '.env.local' >> .gitignore"
echo "  echo '.env.production' >> .gitignore"
