#!/bin/bash
# ─────────────────────────────────────────────────────────
#  HZL AI · Pre-flight Check
#  Usage: bash ~/jarvis/preflight.sh
# ─────────────────────────────────────────────────────────

PASS=0; FAIL=0; WARN=0
JARVIS="$HOME/jarvis"

grn='\033[0;32m'; red='\033[0;31m'; yel='\033[0;33m'; nc='\033[0m'; bold='\033[1m'
ok()   { echo -e "  ${grn}✓${nc}  $1"; ((PASS++)); }
fail() { echo -e "  ${red}✗${nc}  $1"; ((FAIL++)); }
warn() { echo -e "  ${yel}!${nc}  $1"; ((WARN++)); }
hdr()  { echo -e "\n${bold}$1${nc}"; }

set -a; source ~/jarvis/.env; set +a
if [ -f "$JARVIS/.env" ]; then set -a; source "$JARVIS/.env"; set +a; fi

echo -e "\n${bold}HZL AI · Pre-flight Check${nc}"
echo "─────────────────────────────────────────────"

# ── 1. ENV VARS ──────────────────────────────────
hdr "1. Environment Variables"
if [ -n "$ANTHROPIC_API_KEY" ]; then ok "ANTHROPIC_API_KEY is set"; else fail "ANTHROPIC_API_KEY is MISSING"; fi
[ -n "$ELEVENLABS_API_KEY" ] && ok "ELEVENLABS_API_KEY is set" || fail "ELEVENLABS_API_KEY is MISSING"
[ -n "$WEATHER_API_KEY"    ] && ok "WEATHER_API_KEY is set"    || fail "WEATHER_API_KEY is MISSING"

# ── 2. CORE FILES ────────────────────────────────
hdr "2. Core Files (~/jarvis/)"
for f in main.py brain.py voice.py memory.py gmail.py gcal.py spotify.py morning_brief.py weather.py hzl_ws.py start.sh; do
  [ -f "$JARVIS/$f" ] && ok "$f" || fail "$f NOT FOUND"
done

[ -f "$JARVIS/credentials.json" ] && ok "credentials.json" || fail "credentials.json MISSING"

if [ -f "$JARVIS/token.json" ]; then
  AGE=$(( ($(date +%s) - $(date -r "$JARVIS/token.json" +%s)) / 3600 ))
  [ $AGE -gt 168 ] \
    && warn "token.json is ${AGE}h old — may need re-auth (run: python3 $JARVIS/gmail.py)" \
    || ok "token.json (${AGE}h old)"
else
  fail "token.json MISSING — run Google OAuth flow first"
fi

# ── 3. UI FILE ───────────────────────────────────
hdr "3. UI File"
[ -f "$JARVIS/ui/hazel-v5.html" ] && ok "hazel-v5.html in place" || fail "hazel-v5.html NOT FOUND in $JARVIS/ui/"

# ── 4. PYTHON DEPS ───────────────────────────────
hdr "4. Python Dependencies"
check_py() { python3 -c "import $1" 2>/dev/null && ok "python: $1" || fail "python: $1 not installed  →  pip install $2 --break-system-packages"; }
check_py websockets          websockets
check_py anthropic           anthropic
check_py whisper             openai-whisper
check_py requests            requests
check_py sqlite3             "(built-in)"
check_py googleapiclient     google-api-python-client
check_py google.auth.transport google-auth-httplib2

# ── 5. AUDIO ─────────────────────────────────────
hdr "5. Audio Hardware"
if command -v arecord &>/dev/null; then
  ok "arecord available"
  MIC=$(arecord -l 2>/dev/null | grep -i "card" | head -1)
  [ -n "$MIC" ] && ok "Mic detected: $MIC" || warn "No mic detected — check USB mic"
else
  fail "arecord not found  →  sudo apt install alsa-utils"
fi
command -v mpg123 &>/dev/null && ok "mpg123 available" || fail "mpg123 not found  →  sudo apt install mpg123"

# ── 6. WEBSOCKET PORT ────────────────────────────
hdr "6. WebSocket Port"
ss -tlnp 2>/dev/null | grep -q ":8765" \
  && warn "Port 8765 already in use — hzl_ws.py may already be running" \
  || ok "Port 8765 is free"

# ── 7. ANTHROPIC API ─────────────────────────────
hdr "7. Anthropic API"
if [ -n "$ANTHROPIC_API_KEY" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 \
    https://api.anthropic.com/v1/models \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" 2>/dev/null)
  [ "$STATUS" = "200" ] && ok "Anthropic API key valid" \
  || { [ "$STATUS" = "401" ] && fail "Anthropic API key INVALID" || warn "Anthropic returned HTTP $STATUS"; }
fi

# ── 8. ELEVENLABS ────────────────────────────────
hdr "8. ElevenLabs"
if [ -n "$ELEVENLABS_API_KEY" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 \
    "https://api.elevenlabs.io/v1/voices/Uc7anshoV8mdBhDnEZEX" \
    -H "xi-api-key: $ELEVENLABS_API_KEY" 2>/dev/null)
  [ "$STATUS" = "200" ] && ok "ElevenLabs: Hazel voice ID confirmed" \
  || { [ "$STATUS" = "404" ] && fail "Voice ID not found" \
  || { [ "$STATUS" = "401" ] && fail "ElevenLabs API key INVALID" \
  || warn "ElevenLabs returned HTTP $STATUS"; }; }
fi

# ── 9. WEATHER API ───────────────────────────────
hdr "9. OpenWeatherMap"
if [ -n "$WEATHER_API_KEY" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 \
    "https://api.openweathermap.org/data/2.5/weather?q=Garden+City,NY,US&appid=$WEATHER_API_KEY" 2>/dev/null)
  [ "$STATUS" = "200" ] && ok "OpenWeatherMap API key valid" \
  || { [ "$STATUS" = "401" ] && fail "OpenWeatherMap API key INVALID" \
  || warn "OpenWeatherMap returned HTTP $STATUS (key may still be activating — wait 10 min)"; }
fi

# ── 10. MODEL + VOICE STRINGS ────────────────────
hdr "10. Model & Voice Strings"
BRAIN="$JARVIS/brain.py"
VOICE_PY="$JARVIS/voice.py"
[ -f "$BRAIN" ]    && grep -q "claude-haiku-4-5-20251001" "$BRAIN"    && ok "Haiku model string versioned" || warn "Check haiku model string in brain.py"
[ -f "$BRAIN" ]    && grep -q "claude-sonnet-4-5" "$BRAIN"            && ok "Sonnet model string present"
[ -f "$VOICE_PY" ] && grep -q "Uc7anshoV8mdBhDnEZEX" "$VOICE_PY"     && ok "Hazel voice ID confirmed in voice.py" || fail "Wrong voice ID in voice.py"

# ── 11. WS CONTRACT ──────────────────────────────
hdr "11. WebSocket Message Contract"
WS="$JARVIS/hzl_ws.py"
if [ -f "$WS" ]; then
  for msg in chat action start_listening stop_listening response speaking listening thinking idle music_state; do
    grep -q "$msg" "$WS" && ok "WS handles: '$msg'" || warn "WS missing handler: '$msg'"
  done
else
  fail "hzl_ws.py not found"
fi

# ── SUMMARY ──────────────────────────────────────
echo ""
echo "─────────────────────────────────────────────"
echo -e "${bold}Results: ${grn}${PASS} passed${nc}  ${red}${FAIL} failed${nc}  ${yel}${WARN} warnings${nc}"
echo ""
if   [ $FAIL -gt 0 ]; then echo -e "${red}Fix failures before starting Hazel.${nc}"
elif [ $WARN -gt 0 ]; then echo -e "${yel}Warnings are non-critical — safe to start.${nc}"
else                        echo -e "${grn}All clear. Run: bash $JARVIS/start.sh${nc}"
fi
echo ""
