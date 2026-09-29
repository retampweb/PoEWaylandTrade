#!/usr/bin/env python3
"""
PoE Shortcut Daemon — reads keyboard events directly via evdev (/dev/input).
Works in any Wayland compositor, any window, even fullscreen games.
Requires user in 'input' group: sudo usermod -aG input $USER (then re-login).

Usage:
    python3 shortcut_daemon.py          # foreground
    python3 shortcut_daemon.py --start  # install autostart + launch background
"""
import os, sys, subprocess, asyncio, time
from pathlib import Path
import evdev
from evdev import ecodes as e
from keyboards import find_keyboards

DIR = Path(__file__).parent.resolve()

_CTRL = {e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL}
_ALT  = {e.KEY_LEFTALT, e.KEY_RIGHTALT}

SHORTCUTS = [
    {
        'trigger': e.KEY_D,
        'label':   'PoE Price Check',
        'command': ['/usr/bin/python3', str(DIR / 'poecheck.py')],
    },
    {
        'trigger': e.KEY_S,
        'label':   'PoE Stash Scan',
        'command': ['/usr/bin/python3', str(DIR / 'poestash.py')],
    },
]

# Some keyboards expose several event nodes that all report the same keypress
_DEBOUNCE_S = 0.8
_last_fire = 0.0


def _fire(s: dict):
    global _last_fire
    now = time.monotonic()
    if now - _last_fire < _DEBOUNCE_S:
        return
    _last_fire = now
    print(f'→ {s["label"]}', flush=True)
    subprocess.Popen(
        s['command'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


async def _watch(dev: evdev.InputDevice):
    held: set = set()
    try:
        async for event in dev.async_read_loop():
            if event.type != e.EV_KEY:
                continue
            if event.value == 1:
                held.add(event.code)
                if held & _CTRL and held & _ALT:
                    for s in SHORTCUTS:
                        if event.code == s['trigger']:
                            _fire(s)
            elif event.value == 0:
                held.discard(event.code)
    except OSError as ex:
        print(f'Device {dev.path} lost: {ex}', flush=True)


def run_daemon():
    keyboards = find_keyboards()
    if not keyboards:
        print('ERROR: no keyboard found in /dev/input')
        print('Make sure you are in the "input" group:')
        print('  sudo usermod -aG input $USER  (then re-login)')
        sys.exit(1)

    print(f'Watching {len(keyboards)} keyboard(s):')
    for kb in keyboards:
        print(f'  {kb.path}  {kb.name}')
    print()
    print('  Ctrl+Alt+D  →  Price Check')
    print('  Ctrl+Alt+S  →  Stash Scan')
    print('\nDaemon running. Ctrl+C to stop.\n')

    loop = asyncio.new_event_loop()
    for kb in keyboards:
        loop.create_task(_watch(kb))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass


def install_autostart():
    autostart_dir = Path.home() / '.config' / 'autostart'
    autostart_dir.mkdir(parents=True, exist_ok=True)
    desktop = autostart_dir / 'poe-shortcut-daemon.desktop'
    desktop.write_text(
        '[Desktop Entry]\n'
        'Name=PoE Shortcut Daemon\n'
        f'Exec=/usr/bin/python3 {DIR}/shortcut_daemon.py\n'
        'Type=Application\n'
        'X-KDE-AutostartEnabled=true\n'
    )
    print(f'Autostart installed: {desktop}')
    # pkill -f would match this very process too, so skip our own pid
    r = subprocess.run(['pgrep', '-f', 'shortcut_daemon.py'], capture_output=True, text=True)
    for pid in r.stdout.split():
        if int(pid) != os.getpid():
            subprocess.run(['kill', pid], capture_output=True)
    import time; time.sleep(0.3)
    subprocess.Popen(
        ['/usr/bin/python3', str(DIR / 'shortcut_daemon.py')],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print('Daemon launched in background.')
    print()
    print('  Ctrl+Alt+D  →  Price Check')
    print('  Ctrl+Alt+S  →  Stash Scan')


if __name__ == '__main__':
    if '--start' in sys.argv:
        install_autostart()
    else:
        run_daemon()
