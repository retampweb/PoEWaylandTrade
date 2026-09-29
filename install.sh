#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== PoEWaylandTrade — install ==="

echo "[1/4] Installing packages..."
sudo pacman -S --needed --noconfirm \
    ydotool wl-clipboard python python-pyqt6 python-requests python-evdev

echo "[2/4] Enabling ydotool daemon..."
systemctl --user enable --now ydotool 2>/dev/null || \
    sudo systemctl enable --now ydotool 2>/dev/null || \
    echo "  (could not enable ydotool service — start it manually: ydotoold &)"

echo "[3/4] Keyboard access for the hotkey daemon..."
if ! id -nG "$USER" | grep -qw input; then
    sudo usermod -aG input "$USER"
    # grant access right now so a re-login isn't needed for this session
    sudo setfacl -m "u:$USER:rw" /dev/input/event* /dev/uinput 2>/dev/null || true
    echo "  Added $USER to 'input' group (permanent after next login)."
fi

echo "[4/4] Installing hotkey daemon (KDE autostart)..."
chmod +x "$DIR"/poecheck.py "$DIR"/poestash.py "$DIR"/shortcut_daemon.py
python3 "$DIR/shortcut_daemon.py" --start

echo ""
echo "=== Done! ==="
echo "  Ctrl+Alt+D  — price check (hover an item in game)"
echo "  Ctrl+Alt+S  — stash valuation"
echo ""
echo "For stash scan set \"poesessid\" in ~/.config/poepricecheckwayland/config.json"
