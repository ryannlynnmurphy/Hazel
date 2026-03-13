#!/bin/bash
JARVIS="$HOME/jarvis"
LOG_DIR="$JARVIS/logs"
ENV_FILE="$JARVIS/.env"
mkdir -p "$LOG_DIR"

if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
  echo "✓ Loaded $ENV_FILE"
fi

echo "Stopping any existing HZL processes..."
pkill -f "hzl_ws.py" 2>/dev/null && echo "  Stopped hzl_ws.py"
pkill -f "main.py"   2>/dev/null && echo "  Stopped main.py"
pkill -f "http.server 8082" 2>/dev/null && echo "  Stopped HTTP server"
sleep 1

echo "Starting HTTP server for UI..."
nohup python3 -m http.server 8082 --directory "$JARVIS/ui" >> "$LOG_DIR/http.log" 2>&1 &
HTTP_PID=$!
echo "  ✓ UI at http://localhost:8082/hazel-v5.html"

echo "Starting HZL AI..."
nohup python3 "$JARVIS/main.py" >> "$LOG_DIR/main.log" 2>&1 &
MAIN_PID=$!
echo "  main.py PID: $MAIN_PID"

echo "$HTTP_PID $MAIN_PID" > "$JARVIS/.hzl_pids"
echo ""
echo "───────────────────────────────────────────"
echo "HZL AI is running."
echo "  UI:      http://localhost:8082/hazel-v5.html"
echo "  Logs:    tail -f $LOG_DIR/main.log"
echo "  Stop:    bash $JARVIS/stop.sh"
echo "───────────────────────────────────────────"
