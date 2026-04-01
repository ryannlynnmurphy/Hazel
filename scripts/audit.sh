#!/bin/bash
# HZL Security — Local Audit Script
# Run before major pushes: bash scripts/audit.sh

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'
BOLD='\033[1m'

PASS=0
WARN=0
FAIL=0

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  HZL Security Audit${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

pass() { echo -e "${GREEN}✅ $1${NC}"; ((PASS++)); }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; ((WARN++)); }
fail() { echo -e "${RED}❌ $1${NC}"; ((FAIL++)); }
section() { echo -e "\n${BLUE}── $1 ──${NC}"; }

# ── .gitignore ────────────────────────────────────────────────────────────────
section "gitignore"

if [ -f .gitignore ]; then
  if grep -qE "^\.env\*?$|^\.env\$" .gitignore; then
    pass ".env in .gitignore"
  else
    fail ".env NOT in .gitignore — add it now"
  fi

  if grep -q "\.db$\|\.sqlite" .gitignore; then
    pass "database files in .gitignore"
  else
    warn "database files not in .gitignore"
  fi
else
  fail "no .gitignore found"
fi

# ── .env committed? ───────────────────────────────────────────────────────────
section "Committed secrets"

if git ls-files | grep -qE "^\.env$"; then
  fail ".env is committed to git — remove with: git rm --cached .env"
else
  pass ".env not committed"
fi

if git ls-files | grep -qE "\.pem$|\.key$|token\.json$|credentials\.json$"; then
  fail "Credential files committed — check git ls-files output"
else
  pass "No credential files detected in git"
fi

# ── Hardcoded secrets scan ────────────────────────────────────────────────────
section "Hardcoded secrets"

PATTERNS=(
  "sk-ant-[a-zA-Z0-9\-]+"
  "AKIA[0-9A-Z]{16}"
  "AIza[0-9A-Za-z\-_]{35}"
  "xoxb-[0-9]+"
  "ghp_[a-zA-Z0-9]{36}"
)

FOUND_SECRETS=0
for PATTERN in "${PATTERNS[@]}"; do
  MATCHES=$(grep -rE "$PATTERN" --include="*.py" --include="*.ts" --include="*.js" \
    --exclude-dir=node_modules --exclude-dir=.git . 2>/dev/null || true)
  if [ -n "$MATCHES" ]; then
    fail "Possible secret found matching: $PATTERN"
    FOUND_SECRETS=1
  fi
done

if [ $FOUND_SECRETS -eq 0 ]; then
  pass "No hardcoded secrets detected"
fi

# ── Pre-commit hook ───────────────────────────────────────────────────────────
section "Pre-commit hook"

if [ -f .git/hooks/pre-commit ] && [ -x .git/hooks/pre-commit ]; then
  pass "Pre-commit hook installed and executable"
else
  warn "Pre-commit hook not installed — run: bash scripts/setup-hooks.sh"
fi

# ── Python deps ───────────────────────────────────────────────────────────────
section "Python dependencies"

if command -v pip-audit &> /dev/null; then
  if [ -f requirements.txt ]; then
    echo "Running pip-audit..."
    pip-audit -r requirements.txt -q && pass "No Python vulnerability advisories" \
      || warn "Python vulnerabilities found — review above"
  else
    warn "No requirements.txt found"
  fi
else
  warn "pip-audit not installed — run: pip install pip-audit"
fi

# ── Node deps ─────────────────────────────────────────────────────────────────
section "Node.js dependencies"

if [ -f package.json ]; then
  if command -v npm &> /dev/null; then
    npm audit --audit-level=high --silent 2>/dev/null \
      && pass "No high-severity npm vulnerabilities" \
      || warn "npm audit found issues — run: npm audit"
  fi
else
  echo "No package.json — skipping"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}PASS: $PASS${NC}  ${YELLOW}${BOLD}WARN: $WARN${NC}  ${RED}${BOLD}FAIL: $FAIL${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ $FAIL -gt 0 ]; then
  echo -e "${RED}Fix failures before pushing to GitHub.${NC}"
  exit 1
elif [ $WARN -gt 0 ]; then
  echo -e "${YELLOW}Review warnings before your next major push.${NC}"
  exit 0
else
  echo -e "${GREEN}All checks passed. Ship it.${NC}"
  exit 0
fi
