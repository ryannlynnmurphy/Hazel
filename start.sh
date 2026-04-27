#!/bin/bash
# Scatter · Start Script
# Starts orchestrator, then WebSocket server, then UI

HZL_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$HZL_DIR" || exit 1
LOG_DIR="$HZL_DIR/logs"
ENV_FILE="$HZL_DIR/.env"
PID_FILE="$HZL_DIR/.hzl_pids"
mkdir -p "$LOG_DIR"

# Debian/Ubuntu (PEP 668): hzl-cluster is in .venv. Prepend venv site-packages to PYTHONPATH
# so the same system python3 (whisper, spotipy, etc.) can import hzl_cluster.
if [ -x "$HZL_DIR/.venv/bin/python3" ]; then
  _VENV_SPK=$("$HZL_DIR/.venv/bin/python3" -c "import site; p=[x for x in site.getsitepackages() if 'site-packages' in x]; print(p[-1] if p else '')" 2>/dev/null) || _VENV_SPK=
  if [ -n "$_VENV_SPK" ] && [ -d "$_VENV_SPK" ]; then
    export PYTHONPATH="$_VENV_SPK${PYTHONPATH:+:$PYTHONPATH}"
  fi
  # Python 3.12 + glibc: getaddrinfo("", port) can fail; hzl_cluster used "" for UDP bind
  _HZL_NET=$("$HZL_DIR/.venv/bin/python3" -c "import hzl_cluster.network as n; print(n.__file__)" 2>/dev/null) || _HZL_NET=
  if [ -n "$_HZL_NET" ] && [ -f "$_HZL_NET" ] && grep -qF 'local_addr=("",' "$_HZL_NET" 2>/dev/null; then
    sed -i 's/local_addr=("", self.discovery_port)/local_addr=("0.0.0.0", self.discovery_port)/' "$_HZL_NET"
  fi
fi

if [ -f "$ENV_FILE" ]; then
  # Ignore stray \r from Windows-saved .env (avoids: $'\r': command not found)
  set -a; source <(tr -d '\r' < "$ENV_FILE"); set +a
  echo "[+] Loaded $ENV_FILE"
fi

: "${HZL_WS_HOST:=0.0.0.0}"
export HZL_WS_HOST

# hzl_cluster defaults to a config inside the pip package; use the repo’s file
if [ -f "$HZL_DIR/hzl_config.yaml" ]; then
  export HZL_CONFIG="$HZL_DIR/hzl_config.yaml"
fi

echo "[*] Stopping any existing Scatter processes..."
pkill -f "hzl_orchestrator.py" 2>/dev/null && echo "    Stopped hzl_orchestrator.py"
pkill -f "hzl_ws.py" 2>/dev/null && echo "    Stopped hzl_ws.py"
pkill -f "main.py"   2>/dev/null && echo "    Stopped main.py"
pkill -f "http.server 8082" 2>/dev/null && echo "    Stopped HTTP server"
sleep 1

# 1. Start orchestrator (must be up before hzl_ws.py)
echo "[*] Starting Scatter orchestrator..."
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
echo "    UI at http://localhost:8082/  (Scatter OS → scatter.html)"

# 3. Start main + WebSocket
echo "[*] Starting Scatter assistant..."
nohup python3 "$HZL_DIR/main.py" >> "$LOG_DIR/main.log" 2>&1 &
MAIN_PID=$!
echo "    main.py PID: $MAIN_PID"

echo "$ORCH_PID $HTTP_PID $MAIN_PID" > "$PID_FILE"
echo ""
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "-------------------------------------------"
echo "Scatter is running."
echo "  Orchestrator: http://localhost:9000/status"
echo "  UI (this machine):  http://localhost:8082/"
if [ -n "$LAN_IP" ]; then
  echo "  UI (phone/tablet):  http://${LAN_IP}:8082/  (same Wi-Fi — not http://localhost on the phone)"
fi
echo "  WebSocket:    ws://<same-host-as-browser>:8765"
echo "  Logs:         tail -f $LOG_DIR/orchestrator.log"
echo "                tail -f $LOG_DIR/main.log"
echo "  Stop:         bash $HZL_DIR/stop.sh"
echo "-------------------------------------------"
