#!/usr/bin/env python3
"""
Set up KDE global shortcuts for poecheck and poestash.
KDE Plasma 5: writes khotkeysrc + restarts khotkeys daemon.
KDE Plasma 6: khotkeys was removed — prints manual setup guide.
"""
import subprocess, sys, shutil
from pathlib import Path

DIR = Path(__file__).parent.resolve()

_PRICE_CMD  = f'python3 {DIR}/poecheck.py'
_STASH_CMD  = f'python3 {DIR}/poestash.py'

_PRICE_KEYS = ['Ctrl+Alt+D', 'Ctrl+Alt+P', 'Ctrl+F9', 'F9']
_STASH_KEYS = ['Ctrl+Alt+S', 'Ctrl+Alt+V', 'Ctrl+F10', 'F10']


# ------------------------------------------------------------------ helpers

def _kde_version() -> int:
    try:
        r = subprocess.run(['plasmashell', '--version'], capture_output=True, text=True)
        ver = r.stdout.strip()  # e.g. "plasmashell 6.3.4"
        return int(ver.split()[-1].split('.')[0])
    except Exception:
        return 6


def _hotkey_used(shortcut: str) -> bool:
    norm = shortcut.lower().replace(' ', '')
    for fname in ('khotkeysrc', 'kglobalshortcutsrc'):
        f = Path.home() / '.config' / fname
        if f.exists() and norm in f.read_text().lower().replace(' ', ''):
            return True
    return False


def _find_free(candidates: list[str]) -> str:
    for key in candidates:
        if not _hotkey_used(key):
            return key
    return candidates[0]  # fallback to first even if taken


# ------------------------------------------------------------------ KDE 5

def _kwrite(group: str, key: str, value: str):
    subprocess.run(
        ['kwriteconfig6', '--file', 'khotkeysrc',
         '--group', group, '--key', key, value],
        check=True, capture_output=True,
    )


def _kread(group: str, key: str, default: str = '') -> str:
    r = subprocess.run(
        ['kreadconfig6', '--file', 'khotkeysrc',
         '--group', group, '--key', key, '--default', default],
        capture_output=True, text=True,
    )
    return r.stdout.strip()


def _add_shortcut_kde5(name: str, command: str, shortcut: str):
    count = int(_kread('Data', 'DataCount', '0'))
    idx   = count + 1
    _kwrite('Data', 'DataCount', str(idx))

    base = f'Data_{idx}'
    _kwrite(base, 'Comment',     name)
    _kwrite(base, 'DataCount',   '1')
    _kwrite(base, 'Enabled',     'true')
    _kwrite(base, 'Name',        name)
    _kwrite(base, 'SystemGroup', '0')
    _kwrite(base, 'Type',        'SIMPLE_ACTION_DATA')

    trig = f'{base}_1'
    _kwrite(trig, 'Comment', f'Trigger for {name}')
    _kwrite(trig, 'Enabled', 'true')
    _kwrite(trig, 'Name',    'Trigger 0')
    _kwrite(trig, 'Type',    'SHORTCUT')

    _kwrite(f'{base}_1Triggers0', 'Key',  shortcut)
    _kwrite(f'{base}_1Triggers0', 'Type', 'SHORTCUT')

    _kwrite(f'{base}Actions',  'ActionsCount', '1')
    _kwrite(f'{base}Actions0', 'CommandURL',   command)
    _kwrite(f'{base}Actions0', 'Description',  f'Run {name}')
    _kwrite(f'{base}Actions0', 'Name',         'Command 0')
    _kwrite(f'{base}Actions0', 'Type',         'COMMAND_URL')

    print(f'  ✓  {name:30s} → {shortcut}')


def _setup_kde5(hk_price: str, hk_stash: str):
    print('Registering KDE shortcuts (KDE5 mode):')
    _add_shortcut_kde5('PoE Price Check', _PRICE_CMD, hk_price)
    _add_shortcut_kde5('PoE Stash Scan',  _STASH_CMD, hk_stash)

    # Restart khotkeys daemon
    subprocess.run(['kquitapp6', 'khotkeys'], capture_output=True)
    import time; time.sleep(0.5)
    for binary in ('khotkeys',):
        if shutil.which(binary):
            subprocess.Popen([binary], start_new_session=True)
            break

    print()
    print(f'Done! Shortcuts active after ~1s:')
    print(f'  Price check : {hk_price}')
    print(f'  Stash scan  : {hk_stash}')


# ------------------------------------------------------------------ KDE 6 guide

def _setup_kde6_guide(hk_price: str, hk_stash: str):
    print()
    print('═' * 60)
    print('  KDE Plasma 6 — add shortcuts manually (2 minutes)')
    print('═' * 60)
    print()
    print('1. Open: System Settings → Shortcuts → Custom Shortcuts')
    print()
    print('2. Click  Edit → New → Global Shortcut → Command/URL')
    print()
    print('3. Fill in for PRICE CHECK:')
    print(f'     Name    :  PoE Price Check')
    print(f'     Trigger :  {hk_price}')
    print(f'     Action  :  {_PRICE_CMD}')
    print()
    print('4. Click  Edit → New → Global Shortcut → Command/URL  again')
    print()
    print('5. Fill in for STASH SCAN:')
    print(f'     Name    :  PoE Stash Scan')
    print(f'     Trigger :  {hk_stash}')
    print(f'     Action  :  {_STASH_CMD}')
    print()
    print('6. Click Apply')
    print()
    print('═' * 60)
    print()


# ------------------------------------------------------------------ main

def main():
    if not shutil.which('kwriteconfig6'):
        print('ERROR: kwriteconfig6 not found. Is KDE installed?')
        sys.exit(1)

    hk_price = _find_free(_PRICE_KEYS)
    hk_stash = _find_free(_STASH_KEYS)

    kde_ver = _kde_version()
    print(f'Detected KDE Plasma {kde_ver}')

    if kde_ver >= 6 or not shutil.which('khotkeys'):
        _setup_kde6_guide(hk_price, hk_stash)
    else:
        _setup_kde5(hk_price, hk_stash)


if __name__ == '__main__':
    main()
