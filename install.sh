#!/bin/bash
# ============================================================
#  HZL AI -- Hazel Install Script
#  Run once on a fresh Raspberry Pi 5
# ============================================================

set -e
HZL_DIR="$HOME/Hazel"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[x]${NC} $1"; exit 1; }

echo ""
echo "  HZL AI -- Hazel Personal Assistant"
echo "  Install Script"
echo ""

echo "[ 1/9 ] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv chromium-browser alsa-utils mpg123 ffmpeg git curl wget sqlite3 > /dev/null
ok "System packages installed"

echo "[ 2/9 ] Installing Python packages..."
pip install --break-system-packages -q \
  anthropic elevenlabs openai-whisper faster-whisper websockets requests \
  google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client \
  spotipy PyGithub todoist-api-python schedule python-dotenv
ok "Core Python packages installed"

echo "[ 3/9 ] Installing cluster packages..."
pip install --break-system-packages -q aiohttp psutil pyyaml
ok "Cluster packages installed (aiohttp, psutil, pyyaml)"

echo "[ 4/9 ] Setting up Piper TTS..."
PIPER_DIR="$HOME/piper"
if [ ! -f "$PIPER_DIR/piper" ]; then
    mkdir -p "$PIPER_DIR"
    wget -q "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz" -O /tmp/piper.tar.gz
    tar -xzf /tmp/piper.tar.gz -C "$PIPER_DIR" --strip-components=1
    ok "Piper downloaded"
else
    ok "Piper already installed"
fi
mkdir -p "$HZL_DIR/voices"
if [ ! -f "$HZL_DIR/voices/en_US-lessac-medium.onnx" ]; then
    warn "Download Piper voice manually from huggingface.co/rhasspy/piper-voices"
fi

echo "[ 5/9 ] Checking Hazel directory..."
[ ! -d "$HZL_DIR" ] && fail "~/Hazel not found -- clone the repo first"
ok "Hazel directory found at $HZL_DIR"

echo "[ 6/9 ] Setting up environment..."
if [ ! -f "$HZL_DIR/.env" ]; then
    cp "$HZL_DIR/.env.example" "$HZL_DIR/.env"
    warn ".env created from template -- fill in your API keys: nano $HZL_DIR/.env"
else
    ok ".env already exists"
fi

echo "[ 7/9 ] Checking Google OAuth..."
[ ! -f "$HZL_DIR/credentials.json" ] && warn "credentials.json missing -- see console.cloud.google.com" || ok "credentials.json found"
[ ! -f "$HZL_DIR/token.json" ] && warn "token.json missing -- run: cd ~/Hazel && python3 gcal.py" || ok "token.json found"

echo "[ 8/9 ] Setting hostname for cluster..."
CURRENT_HOST=$(hostname)
if [ "$CURRENT_HOST" != "hazel-core" ]; then
    echo "    Current hostname: $CURRENT_HOST"
    read -p "    Set hostname to 'hazel-core'? [y/N] " yn
    if [ "$yn" = "y" ] || [ "$yn" = "Y" ]; then
        sudo hostnamectl set-hostname hazel-core
        ok "Hostname set to hazel-core (reboot for full effect)"
    else
        warn "Hostname not changed -- cluster config expects 'hazel-core'"
    fi
else
    ok "Hostname is hazel-core"
fi

echo "[ 9/9 ] Installing systemd services..."
read -p "    Install systemd services for auto-start? [y/N] " yn
if [ "$yn" = "y" ] || [ "$yn" = "Y" ]; then
    sudo bash "$HZL_DIR/scripts/install-services.sh"
    ok "Systemd services installed"
else
    ok "Skipped systemd install (use bash start.sh for manual start)"
fi

echo ""
echo "-------------------------------------------"
echo "  Hazel install complete!"
echo "  1. Fill in API keys:  nano $HZL_DIR/.env"
echo "  2. Pre-flight check:  bash $HZL_DIR/preflight.sh"
echo "  3. Launch:            bash $HZL_DIR/start.sh"
echo "-------------------------------------------"
