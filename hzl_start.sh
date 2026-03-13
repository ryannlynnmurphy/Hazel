#!/bin/bash
export DISPLAY=:0
source /home/ryannlynnmurphy/jarvis/.env 2>/dev/null

for t in lxterminal xfce4-terminal xterm; do
  if command -v $t &>/dev/null; then
    $t \
      --title="HZL AI" \
      -e "bash -c 'cd /home/ryannlynnmurphy/jarvis && bash start.sh; exec bash'" &
    disown
    break
  fi
done
