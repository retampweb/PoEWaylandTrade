"""Window setup shared by the overlay and stash windows."""
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# KWin always stacks an active fullscreen window above "keep above" windows.
# Override-redirect X11 windows (BypassWindowManagerHint) go to KWin's
# unmanaged layer, the only one above fullscreen. They never get keyboard
# focus, so Esc is read from evdev instead (EscWatcher).
OVERLAY_FLAGS = (
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.X11BypassWindowManagerHint
    | Qt.WindowType.Tool
)


class EscWatcher(QThread):
    pressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._stop = False

    def run(self):
        try:
            from evdev import ecodes
            from keyboards import watch_key
        except ImportError:
            return
        watch_key(ecodes.KEY_ESC, self.pressed.emit, lambda: self._stop)

    def stop(self):
        self._stop = True
        self.wait(500)
