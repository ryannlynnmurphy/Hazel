#!/bin/bash
# ─────────────────────────────────────────────────────
#  HZL AI · Start Script  (start.sh)
#  Usage: bash start.sh
#  Starts: hzl_ws.py → main.py
#  Serves: hazel-v5.html on http://localhost:8080
# ─────────────────────────────────────────────────────

JARVIS="$HOME/jarvis"
LOG_DIR="$JARVIS/logs"
ENV_FILE="$JARVIS/.env"

mkdir -p "$LOG_DIR"

# ── Load .env if present ──────────────────────────
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
  echo "✓ Loaded $ENV_FILE"
else
  echo "! No .env file found at $JARVIS/.env — relying on shell environment"
fi

# ── Kill any existing HZL processes ───────────────
echo "Stopping any existing HZL processes..."
pkill -f "hzl_ws.py"  2>/dev/null && echo "  Stopped hzl_ws.py"
pkill -f "main.py"    2>/dev/null && echo "  Stopped main.py"
pkill -f "python3 -m http.server 8080" 2>/dev/null && echo "  Stopped HTTP server"
sleep 1

# ── Start WebSocket server ─────────────────────────
echo "Starting WebSocket server (hzl_ws.py)..."
nohup python3 "$JARVIS/hzl_ws.py" \
  >> "$LOG_DIR/hzl_ws.log" 2>&1 &
WS_PID=$!
echo "  hzl_ws.py PID: $WS_PID"
sleep 1

# Verify WS started
if ! kill -0 $WS_PID 2>/dev/null; then
  echo "✗ hzl_ws.py failed to start — check $LOG_DIR/hzl_ws.log"
  exit 1
fi
echo "  ✓ WebSocket server running on ws://localhost:8765"

# ── Start HTTP server for UI ───────────────────────
echo "Starting HTTP server for UI..."
nohup python3 -m http.server 8080 \
  --directory "$JARVIS/ui" \
  >> "$LOG_DIR/http.log" 2>&1 &
HTTP_PID=$!
echo "  HTTP PID: $HTTP_PID"
echo "  ✓ UI available at http://localhost:8080/hazel-v5.html"

# ── Start main voice loop ──────────────────────────
echo "Starting main voice loop (main.py)..."
nohup python3 "$JARVIS/main.py" \
  >> "$LOG_DIR/main.log" 2>&1 &
MAIN_PID=$!
echo "  main.py PID: $MAIN_PID"

# ── Write PID file for easy shutdown ──────────────
echo "$WS_PID $HTTP_PID $MAIN_PID" > "$JARVIS/.hzl_pids"

echo ""
echo "───────────────────────────────────────────"
echo "HZL AI is running."
echo "  UI:        http://localhost:8080/hazel-v5.html"
echo "  WebSocket: ws://localhost:8765"
echo "  Logs:      $LOG_DIR/"
echo ""
echo "  To stop:   bash $JARVIS/stop.sh"
echo "  To follow: tail -f $LOG_DIR/hzl_ws.log"
echo "───────────────────────────────────────────"
