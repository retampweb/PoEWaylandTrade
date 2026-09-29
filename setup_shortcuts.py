#!/usr/bin/env python3
"""
Set up KDE global shortcuts for poecheck and poestash.
Writes to ~/.config/khotkeysrc via kwriteconfig6, then restarts khotkeys.
"""
import subprocess, sys, re, shutil
from pathlib import Path

DIR = Path(__file__).parent.resolve()

# Hotkey candidates: first free one wins
_PRICE_KEYS = ['Ctrl+Alt+D', 'Ctrl+Alt+P', 'Ctrl+F9', 'F9']
_STASH_KEYS = ['Ctrl+Alt+S', 'Ctrl+Alt+V', 'Ctrl+F10', 'F10']


def _kread(group: str, key: str, default: str = '') -> str:
    r = subprocess.run(
        ['kreadconfig6', '--file', 'khotkeysrc',
         '--group', group, '--key', key, '--default', default],
        capture_output=True, text=True,
    )
    return r.stdout.strip()


def _kwrite(group: str, key: str, value: str):
    subprocess.run(
        ['kwriteconfig6', '--file', 'khotkeysrc',
         '--group', group, '--key', key, value],
        check=True,
    )


def _hotkey_used(shortcut: str) -> bool:
    """Check both khotkeysrc and kglobalshortcutsrc."""
    norm = shortcut.lower().replace(' ', '')
    for fname in ('khotkeysrc', 'kglobalshortcutsrc'):
        f = Path.home() / '.config' / fname
        if f.exists():
            content = f.read_text().lower().replace(' ', '')
            if norm in content:
                return True
    return False


def _find_free(candidates: list[str]) -> str | None:
    for key in candidates:
        if not _hotkey_used(key):
            return key
    return None


def _add_shortcut(name: str, command: str, shortcut: str):
    count = int(_kread('Data', 'DataCount', '0'))
    idx = count + 1
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

    trig_key = f'{base}_1Triggers0'
    _kwrite(trig_key, 'Key',  shortcut)
    _kwrite(trig_key, 'Type', 'SHORTCUT')

    actions = f'{base}Actions'
    _kwrite(actions, 'ActionsCount', '1')

    action = f'{base}Actions0'
    _kwrite(action, 'CommandURL',  command)
    _kwrite(action, 'Description', f'Run {name}')
    _kwrite(action, 'Name',        'Command 0')
    _kwrite(action, 'Type',        'COMMAND_URL')

    print(f'  ✓  {name:30s} → {shortcut}')


def _reload_khotkeys():
    subprocess.run(['kquitapp6', 'khotkeys'], capture_output=True)
    import time; time.sleep(0.5)
    subprocess.Popen(['khotkeys'], start_new_session=True)


def main():
    if not shutil.which('kwriteconfig6'):
        print('ERROR: kwriteconfig6 not found. Is KDE installed?')
        sys.exit(1)

    hk_price = _find_free(_PRICE_KEYS)
    hk_stash = _find_free(_STASH_KEYS)

    if not hk_price:
        print(f'No free hotkey found for price check. Tried: {_PRICE_KEYS}')
        print('Set one manually in System Settings → Shortcuts → Custom Shortcuts')
        hk_price = None

    if not hk_stash:
        print(f'No free hotkey found for stash scan. Tried: {_STASH_KEYS}')
        hk_stash = None

    if not hk_price and not hk_stash:
        sys.exit(1)

    print('Registering KDE shortcuts:')

    if hk_price:
        _add_shortcut(
            'PoE Price Check',
            f'python3 {DIR}/poecheck.py',
            hk_price,
        )

    if hk_stash:
        _add_shortcut(
            'PoE Stash Scan',
            f'python3 {DIR}/poestash.py',
            hk_stash,
        )

    _reload_khotkeys()

    print()
    print('Done! Shortcuts active after khotkeys restarts (~1s).')
    if hk_price:
        print(f'  Price check : {hk_price}')
    if hk_stash:
        print(f'  Stash scan  : {hk_stash}')
    print()
    print('You can verify in: System Settings → Shortcuts → Custom Shortcuts')


if __name__ == '__main__':
    main()
