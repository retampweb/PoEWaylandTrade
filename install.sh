#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$DIR/poecheck.py"

echo "=== PoE Price Check — install ==="

# 1. System deps
echo "[1/4] Checking system dependencies..."
MISSING=()
command -v ydotool  &>/dev/null || MISSING+=(ydotool)
command -v wl-paste &>/dev/null || MISSING+=(wl-clipboard)
command -v python3  &>/dev/null || MISSING+=(python3)

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Installing: ${MISSING[*]}"
    sudo pacman -S --needed --noconfirm "${MISSING[@]}"
fi

# 2. Enable ydotoold service
echo "[2/4] Enabling ydotool daemon..."
sudo systemctl enable --now ydotool 2>/dev/null || \
    systemctl --user enable --now ydotool 2>/dev/null || \
    echo "  (could not enable ydotool service — start it manually: sudo ydotoold &)"

# Make sure user is in input group (needed for ydotool without sudo)
if ! groups | grep -q input; then
    echo "  Adding $USER to input group (re-login required)..."
    sudo usermod -aG input "$USER"
fi

# 3. Python deps
echo "[3/4] Installing Python dependencies..."
pip install --user -q -r "$DIR/requirements.txt"

# 4. Make scripts executable
chmod +x "$SCRIPT" "$DIR/poestash.py" "$DIR/setup_shortcuts.py"

# 5. KDE shortcuts
echo "[4/4] Setting up KDE shortcuts..."
python3 "$DIR/setup_shortcuts.py"

echo ""
echo "=== Done! ==="
echo ""
echo "IMPORTANT:"
echo "  1. PoE must run in WINDOWED FULLSCREEN (not exclusive fullscreen)"
echo "  2. For stash scan, add to config.json:"
echo "       poesessid   — from browser DevTools → Application → Cookies → pathofexile.com"
echo "       account_name — auto-detected if poesessid is set"
echo ""
echo "Config: ~/.config/poepricecheckwayland/config.json"
