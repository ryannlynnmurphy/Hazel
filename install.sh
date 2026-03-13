#!/bin/bash
# ============================================================
#  HZL AI — Hazel Install Script
#  Pixel Agent Co.
#  Run once on a fresh Raspberry Pi 5
# ============================================================

set -e
JARVIS_DIR="$HOME/jarvis"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo ""
echo "  ██╗  ██╗███████╗██╗      █████╗ ██╗"
echo "  ██║  ██║╚══███╔╝██║     ██╔══██╗██║"
echo "  ███████║  ███╔╝ ██║     ███████║███████║"
echo "  ██╔══██║ ███╔╝  ██║     ██╔══██║██║"
echo "  ██║  ██║███████╗███████╗██║  ██║██║"
echo "  ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝"
echo ""
echo "  Hazel — Personal AI Assistant"
echo "  Pixel Agent Co. — Install Script"
echo ""

echo "[ 1/8 ] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv chromium-browser alsa-utils mpg123 ffmpeg git curl wget sqlite3 > /dev/null
echo -e "\033[0;32m✓ System packages installed\033[0m"

echo "[ 2/8 ] Installing Python packages..."
pip install --break-system-packages -q anthropic elevenlabs openai-whisper faster-whisper websockets requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client spotipy PyGithub todoist-api-python schedule python-dotenv
echo -e "\033[0;32m✓ Python packages installed\033[0m"

echo "[ 3/8 ] Setting up Piper TTS..."
PIPER_DIR="$HOME/piper"
if [ ! -f "$PIPER_DIR/piper" ]; then
    mkdir -p "$PIPER_DIR"
    wget -q "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz" -O /tmp/piper.tar.gz
    tar -xzf /tmp/piper.tar.gz -C "$PIPER_DIR" --strip-components=1
    echo -e "\033[0;32m✓ Piper downloaded\033[0m"
else
    echo -e "\033[0;32m✓ Piper already installed\033[0m"
fi
mkdir -p "$JARVIS_DIR/voices"
if [ ! -f "$JARVIS_DIR/voices/en_US-lessac-medium.onnx" ]; then
    echo -e "\033[1;33m⚠ Download Piper voice manually from huggingface.co/rhasspy/piper-voices\033[0m"
fi

echo "[ 4/8 ] Checking Hazel directory..."
[ ! -d "$JARVIS_DIR" ] && echo -e "\033[0;31m✗ ~/jarvis not found\033[0m" && exit 1
echo -e "\033[0;32m✓ Hazel directory found\033[0m"

echo "[ 5/8 ] Checking environment variables..."
if [ ! -f "$JARVIS_DIR/.env" ]; then
    cat > "$JARVIS_DIR/.env" << 'ENVTEMPLATE'
export ANTHROPIC_API_KEY=your_key_here
export ELEVENLABS_API_KEY=your_key_here
export WEATHER_API_KEY=your_key_here
export GITHUB_TOKEN=your_token_here
export HA_URL=http://localhost:8123
export HA_TOKEN=your_ha_token_here
export JARVIS_CITY=Garden City
export JARVIS_WHISPER_MODEL=base
export JARVIS_RECORD_SECONDS=6
ENVTEMPLATE
    echo -e "\033[1;33m⚠ .env created — fill in your API keys\033[0m"
else
    echo -e "\033[0;32m✓ .env already exists\033[0m"
fi

echo "[ 6/8 ] Checking Google OAuth..."
[ ! -f "$JARVIS_DIR/credentials.json" ] && echo -e "\033[1;33m⚠ credentials.json missing — see console.cloud.google.com\033[0m" || echo -e "\033[0;32m✓ credentials.json found\033[0m"
[ ! -f "$JARVIS_DIR/token.json" ] && echo -e "\033[1;33m⚠ token.json missing — run: cd ~/jarvis && python3 gcal.py\033[0m" || echo -e "\033[0;32m✓ token.json found\033[0m"

echo "[ 7/8 ] Creating desktop launcher..."
mkdir -p "$HOME/Desktop"
cat > "$HOME/Desktop/HZL AI.desktop" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=HZL AI
Comment=Hazel Personal Assistant
Exec=bash $JARVIS_DIR/start.sh
Icon=$JARVIS_DIR/hzl_icon_512.png
Terminal=true
Categories=Utility;
DESKTOP
chmod +x "$HOME/Desktop/HZL AI.desktop"
echo -e "\033[0;32m✓ Desktop launcher created\033[0m"

echo "[ 8/8 ] Enabling SSH..."
sudo systemctl enable ssh --quiet
sudo systemctl start ssh --quiet
echo -e "\033[0;32m✓ SSH enabled\033[0m"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Hazel install complete!"
echo "  1. Fill in API keys:  nano $JARVIS_DIR/.env"
echo "  2. Add credentials:   $JARVIS_DIR/credentials.json"
echo "  3. Authenticate:      cd ~/jarvis && python3 gcal.py"
echo "  4. Launch:            bash $JARVIS_DIR/start.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
