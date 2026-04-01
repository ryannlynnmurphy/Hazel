#!/bin/bash
# Install HZL systemd services on Pi
# Run with: sudo bash scripts/install-services.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[*] Installing HZL systemd services..."

for svc in hzl-orchestrator.service hzl-hazel.service hzl-ui.service; do
  cp "$SCRIPT_DIR/$svc" /etc/systemd/system/
  echo "    Installed $svc"
done

systemctl daemon-reload
echo "[+] Daemon reloaded"

systemctl enable hzl-orchestrator hzl-hazel hzl-ui
echo "[+] Services enabled for boot"

echo ""
echo "Start everything:"
echo "  sudo systemctl start hzl-orchestrator hzl-hazel hzl-ui"
echo ""
echo "Check status:"
echo "  sudo systemctl status hzl-orchestrator hzl-hazel hzl-ui"
echo ""
echo "View logs:"
echo "  journalctl -u hzl-orchestrator -f"
echo "  journalctl -u hzl-hazel -f"
