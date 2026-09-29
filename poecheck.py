#!/usr/bin/env python3
"""
PoE Price Check — KDE Wayland / XWayland overlay.
Bind to a KDE custom shortcut (e.g. Ctrl+Alt+D).
"""
import os, sys, subprocess, time, fcntl, shutil
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


# ctrl, alt, shift, meta (both sides)
_MODIFIERS = {29, 97, 56, 100, 42, 54, 125, 126}
_KEY_LEFTCTRL, _KEY_C = 29, 46


def wait_modifiers_released(timeout: float = 1.5):
    """Injecting Ctrl+C while the user still holds Ctrl+Alt from the hotkey
    would reach the game as Ctrl+Alt+C, so wait for a clean keyboard state."""
    try:
        from keyboards import find_keyboards
    except ImportError:
        time.sleep(0.3)
        return
    devs = find_keyboards()
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if not any(_MODIFIERS & set(d.active_keys()) for d in devs):
                return
            time.sleep(0.02)
    finally:
        for d in devs:
            d.close()


def inject_copy():
    # ydotool 1.x takes raw keycodes; names like "ctrl+c" are silently ignored
    subprocess.run(
        ['ydotool', 'key', '-d', '30',
         f'{_KEY_LEFTCTRL}:1', f'{_KEY_C}:1', f'{_KEY_C}:0', f'{_KEY_LEFTCTRL}:0'],
        check=False, capture_output=True,
    )


def read_clipboard() -> str:
    r = subprocess.run(['wl-paste', '--no-newline'], capture_output=True, text=True)
    text = r.stdout if r.returncode == 0 else ''
    if 'Rarity:' not in text and shutil.which('xsel'):
        # Wine can end up on the X11 clipboard instead of the Wayland one
        r = subprocess.run(['xsel', '-ob'], capture_output=True, text=True)
        if r.returncode == 0 and 'Rarity:' in r.stdout:
            return r.stdout
    return text


def wait_for_item(timeout: float = 2.0) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.05)
        text = read_clipboard()
        if 'Rarity:' in text:
            return text
    return None


def check_deps():
    missing = [cmd for cmd in ('ydotool', 'wl-paste')
               if subprocess.run(['which', cmd], capture_output=True).returncode != 0]
    if missing:
        print(f'Missing: {", ".join(missing)}  →  sudo pacman -S ydotool wl-clipboard')
        sys.exit(1)


_LOG = open('/tmp/poecheck_debug.log', 'a')

def _log(msg):
    import datetime
    print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}] {msg}', file=_LOG, flush=True)


def main():
    _log('--- poecheck started ---')
    if not _acquire_lock():
        _log('lock busy, exit')
        sys.exit(0)

    check_deps()
    cfg = Config.load()
    _log(f'league={cfg.league}')

    # Clear first so re-checking the same item still registers as new
    subprocess.run(['wl-copy', '--clear'], capture_output=True)
    wait_modifiers_released()
    inject_copy()
    _log('ydotool ctrl+c sent')

    item_text = wait_for_item()
    if not item_text:
        _log('no item in clipboard after 2s — exit')
        sys.exit(0)

    _log(f'got item: {repr(item_text[:80])}')
    item = parse_item(item_text)
    if not item or not item.rarity:
        _log(f'parse failed: item={item}')
        sys.exit(0)

    _log(f'parsed: {item.display_name} ({item.rarity})')
    db    = StatsDB.get()
    ninja = NinjaClient(cfg.league)
    trade = TradeClient(cfg.league, cfg.poesessid)

    _log('launching overlay')
    run_overlay(item, db, ninja, trade, cfg)
    sys.exit(0)


if __name__ == '__main__':
    main()
