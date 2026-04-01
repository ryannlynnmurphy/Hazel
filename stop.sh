#!/bin/bash
# HZL AI · Stop Script

HZL_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$HZL_DIR/.hzl_pids"

echo "[*] Stopping HZL AI..."

if [ -f "$PID_FILE" ]; then
  read -r ORCH HTTP MAIN < "$PID_FILE"
  for pid in $MAIN $HTTP $ORCH; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" && echo "    Stopped PID $pid"
    fi
  done
  rm "$PID_FILE"
else
  # Fallback: kill by name
  pkill -f "hzl_orchestrator.py" && echo "    Stopped hzl_orchestrator.py"
  pkill -f "hzl_ws.py" && echo "    Stopped hzl_ws.py"
  pkill -f "main.py"   && echo "    Stopped main.py"
  pkill -f "http.server 8082" && echo "    Stopped HTTP server"
fi

echo "[+] Done."
