#!/bin/bash
# HZL AI · Desktop Launcher (opens in a terminal window on the Pi)
export DISPLAY=:0

HZL_DIR="$HOME/Hazel"
source "$HZL_DIR/.env" 2>/dev/null

for t in lxterminal xfce4-terminal xterm; do
  if command -v $t &>/dev/null; then
    $t \
      --title="HZL AI" \
      -e "bash -c 'cd $HZL_DIR && bash start.sh; exec bash'" &
    disown
    break
  fi
done
