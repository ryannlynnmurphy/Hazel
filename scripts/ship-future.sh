#!/usr/bin/env bash
# ship-future.sh - run after a reboot (or any morning you want the stack sharp).
set -euo pipefail

SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
HZL_DIR="$(cd "$(dirname "$SCRIPT")/.." && pwd)"
BOLD=$'\e[1m'
DIM=$'\e[2m'
GRN=$'\e[32m'
CYN=$'\e[36m'
RST=$'\e[0m'

echo ""
echo "${CYN}${BOLD}  Scatter / Hazel - ship into the future${RST}"
echo "${DIM}  Local voice OS - confabulatory classroom node - no cloud required to care${RST}"
echo ""

if command -v cursor-agent >/dev/null 2>&1; then
  echo "${BOLD}Cursor Agent CLI${RST}"
  echo "  before: $(cursor-agent --version 2>/dev/null || echo '?')"
  if cursor-agent update 2>&1; then
    echo "  ${GRN}after:${RST}  $(cursor-agent --version 2>/dev/null || echo '?')"
  else
    echo "  ${DIM}(update non-fatal)${RST}"
  fi
else
  echo "${DIM}  cursor-agent not in PATH: curl -fsSL https://cursor.com/install | bash${RST}"
fi
echo ""

if dpkg -l 2>/dev/null | grep -q '^ii\s\+cursor\s'; then
  echo "${BOLD}Cursor editor (apt package cursor)${RST}"
  echo "  ${DIM}sudo apt update && sudo apt install --only-upgrade cursor${RST}"
else
  echo "${BOLD}Cursor editor${RST}"
  echo "  ${DIM}https://cursor.com/download - Help, Check for Updates in app.${RST}"
fi
echo ""

echo "${BOLD}Hazel / Scatter repo${RST}  ${DIM}$HZL_DIR${RST}"
if git -C "$HZL_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$HZL_DIR" status -sb
  echo ""
  if ! git -C "$HZL_DIR" remote -v 2>/dev/null | grep -q '^origin'; then
    echo "  ${DIM}No origin remote - add: git remote add origin git@github.com:you/Hazel.git${RST}"
  fi
else
  echo "  (not a git repo)"
fi
echo ""

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [ -n "$IP" ]; then
  echo "${BOLD}LAN URL for phones (same Wi-Fi)${RST}"
  echo "  ${CYN}http://${IP}:8082/hazel-v5.html${RST}"
  echo "  ${DIM}WebSocket: ws://${IP}:8765${RST}"
else
  echo "${DIM}  Could not read LAN IP.${RST}"
fi
echo ""
echo "  ${BOLD}Next:${RST}  cd $HZL_DIR && bash start.sh  - see ${BOLD}SHIP.md${RST}"
echo ""
