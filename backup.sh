#!/bin/bash
# Usage: ./backup.sh "your commit message"
cd ~/jarvis
git add -A
git commit -m "${1:-checkpoint $(date '+%Y-%m-%d %H:%M')}"
git log --oneline -1
