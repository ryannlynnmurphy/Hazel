#!/bin/bash
cd ~/jarvis
source ~/.bashrc
set -a; source .env; set +a

# Kill any existing Hazel processes
pkill -f "main.py" 2>/dev/null
sleep 1

# Free ports (no stray space before sudo)
sudo fuser -k 8765/tcp 2>/dev/null
sudo fuser -k 8766/tcp 2>/dev/null
sleep 1

# Ensure correct speaker card (HDMI card 1)
export JARVIS_SPEAKER_CARD=plughw:1,0
export JARVIS_MIC_CARD=plughw:2,0

# Kill old browser instance
pkill -f "hazel-dynamic" 2>/dev/null
pkill -f "hazel-refined" 2>/dev/null
sleep 1

# Launch UI
DISPLAY=:0 chromium \
  --user-data-dir=/tmp/hazel-profile \
  --app=file:///home/ryannlynnmurphy/jarvis/ui/hazel-dynamic.html \
  --start-maximized \
  --no-first-run \
  --disable-session-crashed-bubble \
  --disable-infobars \
  > /dev/null 2>&1 &

sleep 2
python3 main.py
