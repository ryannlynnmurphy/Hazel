#!/bin/bash
# ---------------------------------------------------------
#  HZL AI -- Pre-flight Check
#  Usage: bash ~/Hazel/preflight.sh
# ---------------------------------------------------------

PASS=0; FAIL=0; WARN=0
HZL="$HOME/Hazel"

grn='\033[0;32m'; red='\033[0;31m'; yel='\033[0;33m'; nc='\033[0m'; bold='\033[1m'
ok()   { echo -e "  ${grn}[+]${nc}  $1"; ((PASS++)); }
fail() { echo -e "  ${red}[x]${nc}  $1"; ((FAIL++)); }
warn() { echo -e "  ${yel}[!]${nc}  $1"; ((WARN++)); }
hdr()  { echo -e "\n${bold}$1${nc}"; }

if [ -f "$HZL/.env" ]; then set -a; source "$HZL/.env"; set +a; fi

echo -e "\n${bold}HZL AI -- Pre-flight Check${nc}"
echo "---------------------------------------------------------"

# -- 1. ENV VARS --
hdr "1. Environment Variables"
[ -n "$ANTHROPIC_API_KEY"  ] && ok "ANTHROPIC_API_KEY is set"  || fail "ANTHROPIC_API_KEY is MISSING"
[ -n "$ELEVENLABS_API_KEY" ] && ok "ELEVENLABS_API_KEY is set" || fail "ELEVENLABS_API_KEY is MISSING"
[ -n "$WEATHER_API_KEY"    ] && ok "WEATHER_API_KEY is set"    || fail "WEATHER_API_KEY is MISSING"

# -- 2. CORE FILES --
hdr "2. Core Files (~/Hazel/)"
for f in main.py brain.py voice.py memory.py gmail.py gcal.py spotify.py hzl_ws.py start.sh; do
  [ -f "$HZL/$f" ] && ok "$f" || fail "$f NOT FOUND"
done
[ -f "$HZL/credentials.json" ] && ok "credentials.json" || fail "credentials.json MISSING"

if [ -f "$HZL/token.json" ]; then
  AGE=$(( ($(date +%s) - $(date -r "$HZL/token.json" +%s)) / 3600 ))
  [ $AGE -gt 168 ] \
    && warn "token.json is ${AGE}h old -- may need re-auth" \
    || ok "token.json (${AGE}h old)"
else
  fail "token.json MISSING -- run Google OAuth flow first"
fi

# -- 3. CLUSTER FILES --
hdr "3. Cluster Layer"
for f in hzl_config.yaml hzl_network.py hzl_router.py hzl_orchestrator.py hzl_ws_integration.py; do
  [ -f "$HZL/$f" ] && ok "$f" || fail "$f NOT FOUND"
done
[ -d "$HZL/hzl_security" ] && ok "hzl_security/" || fail "hzl_security/ directory MISSING"

# -- 4. HOSTNAME --
hdr "4. Hostname"
HOSTNAME=$(hostname)
if grep -q "$HOSTNAME" "$HZL/hzl_config.yaml" 2>/dev/null; then
  ok "Hostname '$HOSTNAME' found in hzl_config.yaml"
else
  warn "Hostname '$HOSTNAME' not in hzl_config.yaml -- cluster may not recognize this node"
fi

# -- 5. UI FILE --
hdr "5. UI File"
[ -f "$HZL/ui/hazel-v5.html" ] && ok "hazel-v5.html in place" || fail "hazel-v5.html NOT FOUND in ui/"

# -- 6. PYTHON DEPS --
hdr "6. Python Dependencies"
check_py() { python3 -c "import $1" 2>/dev/null && ok "python: $1" || fail "python: $1 not installed -> pip install $2 --break-system-packages"; }
check_py websockets          websockets
check_py anthropic           anthropic
check_py aiohttp             aiohttp
check_py psutil              psutil
check_py yaml                pyyaml
check_py requests            requests
check_py sqlite3             "(built-in)"
check_py googleapiclient     google-api-python-client

# -- 7. AUDIO --
hdr "7. Audio Hardware"
if command -v arecord &>/dev/null; then
  ok "arecord available"
  MIC=$(arecord -l 2>/dev/null | grep -i "card" | head -1)
  [ -n "$MIC" ] && ok "Mic detected: $MIC" || warn "No mic detected -- check USB mic"
else
  fail "arecord not found -> sudo apt install alsa-utils"
fi
command -v mpg123 &>/dev/null && ok "mpg123 available" || fail "mpg123 not found -> sudo apt install mpg123"

# -- 8. PORTS --
hdr "8. Network Ports"
ss -tlnp 2>/dev/null | grep -q ":8765" \
  && warn "Port 8765 already in use (hzl_ws.py may be running)" \
  || ok "Port 8765 is free"
ss -tlnp 2>/dev/null | grep -q ":9000" \
  && warn "Port 9000 already in use (orchestrator may be running)" \
  || ok "Port 9000 is free"

# -- 9. ANTHROPIC API --
hdr "9. Anthropic API"
if [ -n "$ANTHROPIC_API_KEY" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 \
    https://api.anthropic.com/v1/models \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" 2>/dev/null)
  [ "$STATUS" = "200" ] && ok "Anthropic API key valid" \
  || { [ "$STATUS" = "401" ] && fail "Anthropic API key INVALID" || warn "Anthropic returned HTTP $STATUS"; }
fi

# -- 10. ELEVENLABS --
hdr "10. ElevenLabs"
if [ -n "$ELEVENLABS_API_KEY" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 \
    "https://api.elevenlabs.io/v1/voices/Uc7anshoV8mdBhDnEZEX" \
    -H "xi-api-key: $ELEVENLABS_API_KEY" 2>/dev/null)
  [ "$STATUS" = "200" ] && ok "ElevenLabs: Hazel voice confirmed" \
  || { [ "$STATUS" = "401" ] && fail "ElevenLabs key INVALID" || warn "ElevenLabs returned HTTP $STATUS"; }
fi

# -- 11. MODEL STRINGS --
hdr "11. Model & Voice Strings"
BRAIN="$HZL/brain.py"
VOICE_PY="$HZL/voice.py"
[ -f "$BRAIN" ] && grep -q "claude-haiku-4-5-20251001" "$BRAIN" && ok "Haiku model string versioned" || warn "Check haiku model string in brain.py"
[ -f "$BRAIN" ] && grep -q "claude-sonnet" "$BRAIN" && ok "Sonnet model string present"
[ -f "$VOICE_PY" ] && grep -q "Uc7anshoV8mdBhDnEZEX" "$VOICE_PY" && ok "Hazel voice ID in voice.py" || fail "Wrong voice ID in voice.py"

# -- 12. WS CONTRACT --
hdr "12. WebSocket Message Contract"
WS="$HZL/hzl_ws.py"
if [ -f "$WS" ]; then
  for msg in chat action start_listening stop_listening response speaking listening thinking idle music_state; do
    grep -q "$msg" "$WS" && ok "WS handles: '$msg'" || warn "WS missing handler: '$msg'"
  done
else
  fail "hzl_ws.py not found"
fi

# -- SUMMARY --
echo ""
echo "---------------------------------------------------------"
echo -e "${bold}Results: ${grn}${PASS} passed${nc}  ${red}${FAIL} failed${nc}  ${yel}${WARN} warnings${nc}"
echo ""
if   [ $FAIL -gt 0 ]; then echo -e "${red}Fix failures before starting Hazel.${nc}"
elif [ $WARN -gt 0 ]; then echo -e "${yel}Warnings are non-critical -- safe to start.${nc}"
else                        echo -e "${grn}All clear. Run: bash $HZL/start.sh${nc}"
fi
echo ""
