#!/bin/bash
# HZL AI · Stop Script

JARVIS="$HOME/jarvis"
PID_FILE="$JARVIS/.hzl_pids"

echo "Stopping HZL AI..."

if [ -f "$PID_FILE" ]; then
  read -r WS HTTP MAIN < "$PID_FILE"
  for pid in $WS $HTTP $MAIN; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" && echo "  Stopped PID $pid"
    fi
  done
  rm "$PID_FILE"
else
  # Fallback: kill by name
  pkill -f "hzl_ws.py" && echo "  Stopped hzl_ws.py"
  pkill -f "main.py"   && echo "  Stopped main.py"
  pkill -f "http.server 8080" && echo "  Stopped HTTP server"
fi

echo "Done."
