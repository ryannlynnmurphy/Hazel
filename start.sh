#!/bin/bash
# HZL AI · Start Script
# Starts orchestrator, then WebSocket server, then UI

HZL_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$HZL_DIR/logs"
ENV_FILE="$HZL_DIR/.env"
PID_FILE="$HZL_DIR/.hzl_pids"
mkdir -p "$LOG_DIR"

if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
  echo "[+] Loaded $ENV_FILE"
fi

echo "[*] Stopping any existing HZL processes..."
pkill -f "hzl_orchestrator.py" 2>/dev/null && echo "    Stopped hzl_orchestrator.py"
pkill -f "hzl_ws.py" 2>/dev/null && echo "    Stopped hzl_ws.py"
pkill -f "main.py"   2>/dev/null && echo "    Stopped main.py"
pkill -f "http.server 8082" 2>/dev/null && echo "    Stopped HTTP server"
sleep 1

# 1. Start orchestrator (must be up before hzl_ws.py)
echo "[*] Starting HZL Orchestrator..."
nohup python3 "$HZL_DIR/hzl_orchestrator.py" >> "$LOG_DIR/orchestrator.log" 2>&1 &
ORCH_PID=$!
echo "    PID: $ORCH_PID"
sleep 1

# Verify orchestrator is alive
if ! kill -0 "$ORCH_PID" 2>/dev/null; then
  echo "[!] Orchestrator failed to start. Check $LOG_DIR/orchestrator.log"
  exit 1
fi
echo "    Orchestrator is running"

# 2. Start HTTP server for UI
echo "[*] Starting UI server..."
nohup python3 -m http.server 8082 --directory "$HZL_DIR/ui" >> "$LOG_DIR/http.log" 2>&1 &
HTTP_PID=$!
echo "    UI at http://localhost:8082/hazel-v5.html"

# 3. Start main + WebSocket
echo "[*] Starting HZL AI..."
nohup python3 "$HZL_DIR/main.py" >> "$LOG_DIR/main.log" 2>&1 &
MAIN_PID=$!
echo "    main.py PID: $MAIN_PID"

echo "$ORCH_PID $HTTP_PID $MAIN_PID" > "$PID_FILE"
echo ""
echo "-------------------------------------------"
echo "HZL AI is running."
echo "  Orchestrator: http://localhost:9000/status"
echo "  UI:           http://localhost:8082/hazel-v5.html"
echo "  Logs:         tail -f $LOG_DIR/orchestrator.log"
echo "                tail -f $LOG_DIR/main.log"
echo "  Stop:         bash $HZL_DIR/stop.sh"
echo "-------------------------------------------"
