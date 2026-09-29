#!/usr/bin/env python3
"""
PoE Price Check — KDE Wayland / XWayland overlay.
Bind to a KDE custom shortcut (e.g. Ctrl+Alt+D).
"""
import os, sys, subprocess, time, fcntl
os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

from config import Config
from parser import parse_item
from stats_db import StatsDB
from trade import TradeClient
from ninja import NinjaClient
from overlay import run_overlay

_LOCK_PATH = '/tmp/poecheck.lock'
_lock_fh = None


def _acquire_lock() -> bool:
    """Single-instance guard — prevents overlay stacking on rapid hotkey presses."""
    global _lock_fh
    try:
        _lock_fh = open(_LOCK_PATH, 'w')
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False  # another instance is running


def inject_copy():
    subprocess.run(['ydotool', 'key', 'ctrl+c'], check=False, capture_output=True)


def read_clipboard() -> str:
    r = subprocess.run(['wl-paste', '--no-newline'], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ''


def wait_for_item(old: str, timeout: float = 2.0) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.1)
        new = read_clipboard()
        if new != old and 'Rarity:' in new:
            return new
    return None


def check_deps():
    missing = [cmd for cmd in ('ydotool', 'wl-paste')
               if subprocess.run(['which', cmd], capture_output=True).returncode != 0]
    if missing:
        print(f'Missing: {", ".join(missing)}  →  sudo pacman -S ydotool wl-clipboard')
        sys.exit(1)


def main():
    if not _acquire_lock():
        sys.exit(0)   # another poecheck is already showing — do nothing

    check_deps()
    cfg = Config.load()

    old = read_clipboard()
    inject_copy()

    item_text = wait_for_item(old)
    if not item_text:
        sys.exit(0)

    item = parse_item(item_text)
    if not item or not item.rarity:
        sys.exit(0)

    db    = StatsDB.get()
    ninja = NinjaClient(cfg.league)
    trade = TradeClient(cfg.league, cfg.poesessid)

    run_overlay(item, db, ninja, trade, cfg)
    sys.exit(0)


if __name__ == '__main__':
    main()
