"""Physical keyboard access via evdev (/dev/input) — works regardless of window focus."""
import glob, select
import evdev
from evdev import ecodes as e


def find_keyboards() -> list:
    devs = []
    for path in sorted(glob.glob('/dev/input/event*')):
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue
        keys = dev.capabilities().get(e.EV_KEY, [])
        # ydotool's virtual keyboard is skipped so injected keys never count as user input
        if 'ydotoold' not in dev.name and e.KEY_D in keys and e.KEY_LEFTCTRL in keys:
            devs.append(dev)
        else:
            dev.close()
    return devs


def watch_key(code: int, on_press, should_stop):
    """Blocking loop: call on_press() each time `code` goes down, until should_stop()."""
    devs = find_keyboards()
    try:
        while devs and not should_stop():
            ready, _, _ = select.select(devs, [], [], 0.1)
            for dev in ready:
                for ev in dev.read():
                    if ev.type == e.EV_KEY and ev.code == code and ev.value == 1:
                        on_press()
    except OSError:
        pass
    finally:
        for dev in devs:
            dev.close()
