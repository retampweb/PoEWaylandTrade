#!/usr/bin/env python3
"""
PoE Stash Valuation — scans all stash tabs and shows market prices.
Requires poesessid in ~/.config/poepricecheckwayland/config.json
"""
import os, sys, fcntl
os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

from config import Config
from ninja import NinjaClient
from stash import StashScanner
from stash_window import run_stash_window

_LOCK_PATH = '/tmp/poestash.lock'
_lock_fh = None


def _acquire_lock() -> bool:
    global _lock_fh
    try:
        _lock_fh = open(_LOCK_PATH, 'w')
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def main():
    if not _acquire_lock():
        sys.exit(0)   # stash window already open

    cfg = Config.load()

    if not cfg.poesessid:
        print('ERROR: poesessid not set in config.')
        print('Edit: ~/.config/poepricecheckwayland/config.json')
        print('Get POESESSID: browser DevTools → Application → Cookies → pathofexile.com')
        sys.exit(1)

    if not cfg.account_name:
        print('ERROR: account_name not set and could not be auto-detected.')
        print('Add "account_name": "YourName" to config.json')
        sys.exit(1)

    ninja   = NinjaClient(cfg.league)
    scanner = StashScanner(cfg.account_name, cfg.league, cfg.poesessid)

    run_stash_window(scanner, ninja, cfg.league)


if __name__ == '__main__':
    main()
