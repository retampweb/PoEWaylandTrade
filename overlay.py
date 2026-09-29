"""PyQt6 overlay window — always-on-top XWayland window with item info + prices."""
import os, sys, subprocess, json
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from qt_common import OVERLAY_FLAGS, EscWatcher
from ninja import NinjaClient, NINJA_RARITIES
from trade import TradeClient, Listing
from parser import ParsedItem

# ------------------------------------------------------------------ palette

_BG       = '#0d0d0d'
_BORDER   = '#3a2a1a'
_TEXT     = '#c8b998'
_DIM      = '#776655'
_UNIQUE   = '#af6025'
_RARE     = '#ffff77'
_MAGIC    = '#8888ff'
_NORMAL   = '#c8c8c8'
_CURRENCY = '#aa9e82'
_GEM      = '#1ba29b'
_MOD      = '#88bb66'
_IMPLICIT = '#8888bb'
_PRICE    = '#ddcc88'
_RED      = '#ff4444'

_RARITY_COLOR = {
    'Unique': _UNIQUE, 'Rare': _RARE, 'Magic': _MAGIC,
    'Normal': _NORMAL, 'Currency': _CURRENCY, 'Gem': _GEM,
    'Divination Card': '#c8c8aa',
}

_STYLE = f"""
QWidget {{
    background: {_BG};
    color: {_TEXT};
    font-size: 11px;
}}
QLabel {{ background: transparent; }}
QPushButton {{
    background: #221a10;
    border: 1px solid {_BORDER};
    color: {_TEXT};
    padding: 3px 10px;
    border-radius: 2px;
    font-size: 11px;
}}
QPushButton:hover {{ background: #332a18; border-color: #665544; }}
QPushButton:disabled {{ color: #443322; border-color: #221a10; }}
"""


# ------------------------------------------------------------------ worker

class FetchThread(QThread):
    done = pyqtSignal(list, str)   # listings, trade_url

    def __init__(self, item: ParsedItem, stat_filters: list,
                 trade: TradeClient, ninja: NinjaClient, max_listings: int):
        super().__init__()
        self.item = item
        self.stat_filters = stat_filters
        self.trade = trade
        self.ninja = ninja
        self.max_listings = max_listings

    def run(self):
        item = self.item

        if item.rarity in NINJA_RARITIES:
            price = self.ninja.get_price(item.display_name, item.links)
            if price:
                div   = price.get('divine_value', 0)
                chaos = price.get('chaos_value', 0)
                if div and div >= 1:
                    amt, cur = round(div, 2), 'divine'
                else:
                    amt, cur = round(chaos, 1), 'chaos'
                listing = Listing(
                    price_amount=amt, price_currency=cur,
                    seller='poe.ninja', age='market avg',
                )
                self.done.emit([listing], '')
                return

        listings, url = self.trade.search_and_fetch(
            item, self.stat_filters, self.max_listings
        )
        self.done.emit(listings, url)


# ------------------------------------------------------------------ helpers

def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f'color: {_BORDER};')
    return f


def _vline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet(f'color: {_BORDER};')
    return f


def _lbl(text: str, color: str = _TEXT, size: int = 11,
         bold: bool = False, wrap: bool = False) -> QLabel:
    w = QLabel(str(text))
    style = f'color: {color}; font-size: {size}px;'
    if bold:
        style += ' font-weight: bold;'
    w.setStyleSheet(style)
    if wrap:
        w.setWordWrap(True)
    return w


# ------------------------------------------------------------------ window

class OverlayWindow(QWidget):
    def __init__(self, item: ParsedItem, stat_filters: list,
                 trade: TradeClient, ninja: NinjaClient, max_listings: int):
        super().__init__()
        self.item = item
        self.trade_url = ''
        self._drag_pos = None
        self._dragged = False

        self.setWindowFlags(OVERLAY_FLAGS)
        self.setStyleSheet(_STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._build(item)
        self.adjustSize()
        self._place()

        self._thread = FetchThread(item, stat_filters, trade, ninja, max_listings)
        self._thread.done.connect(self._on_prices)
        self._thread.start()

        self._esc = EscWatcher()
        self._esc.pressed.connect(self.close)
        self._esc.start()

    # ---------------------------------------------------------------- layout

    def _build(self, item: ParsedItem):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(5)

        # Title bar
        title_row = QHBoxLayout()
        color = _RARITY_COLOR.get(item.rarity, _TEXT)
        title_row.addWidget(_lbl(item.display_name, color, 15, bold=True))
        title_row.addStretch()

        close_btn = QPushButton('✕')
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            f'QPushButton {{ background: transparent; border: none; color: {_DIM}; }}'
            f'QPushButton:hover {{ color: {_RED}; }}'
        )
        close_btn.clicked.connect(self.close)
        title_row.addWidget(close_btn)
        root.addLayout(title_row)

        if item.base_type and item.base_type != item.name:
            root.addWidget(_lbl(item.base_type, _DIM))

        meta = []
        if item.item_level:   meta.append(f'iLvl {item.item_level}')
        if item.quality:      meta.append(f'Q{item.quality}%')
        if item.sockets:      meta.append(item.sockets)
        if item.influences:   meta.append(' / '.join(item.influences))
        if item.is_corrupted: meta.append('Corrupted')
        if item.is_mirrored:  meta.append('Mirrored')
        if meta:
            root.addWidget(_lbl('  ·  '.join(meta), _DIM, 10))

        root.addWidget(_hline())

        cols = QHBoxLayout()
        cols.setSpacing(14)

        # Left: mods
        mods_col = QVBoxLayout()
        mods_col.setSpacing(2)
        mods_col.setContentsMargins(0, 0, 0, 0)

        if item.implicits:
            for mod in item.implicits:
                mods_col.addWidget(_lbl(mod, _IMPLICIT, wrap=True))
            mods_col.addWidget(_hline())

        if not item.is_identified:
            mods_col.addWidget(_lbl('Unidentified', '#ff7733'))
        else:
            for mod in item.explicits:
                mods_col.addWidget(_lbl(mod, _MOD, wrap=True))

        mods_col.addStretch()
        mods_frame = QWidget()
        mods_frame.setLayout(mods_col)
        mods_frame.setMinimumWidth(210)
        mods_frame.setMaximumWidth(270)
        cols.addWidget(mods_frame)

        cols.addWidget(_vline())

        # Right: prices
        self._prices_col = QVBoxLayout()
        self._prices_col.setSpacing(3)
        self._prices_col.setContentsMargins(0, 0, 0, 0)
        self._prices_col.addWidget(_lbl('Loading…', _DIM))
        self._prices_col.addStretch()

        prices_frame = QWidget()
        prices_frame.setLayout(self._prices_col)
        prices_frame.setMinimumWidth(190)
        cols.addWidget(prices_frame)

        root.addLayout(cols)
        root.addWidget(_hline())

        btns = QHBoxLayout()
        btns.addStretch()
        self._browser_btn = QPushButton('Open in Browser')
        self._browser_btn.setEnabled(False)
        self._browser_btn.clicked.connect(self._open_browser)
        btns.addWidget(self._browser_btn)
        root.addLayout(btns)

    # ---------------------------------------------------------------- helpers

    def _place(self):
        # XWayland can't see the cursor over a native Wayland game, so use the
        # position the user last dragged the overlay to, or the right side.
        geo = QApplication.primaryScreen().geometry()
        w, h = self.width(), self.height()
        saved = _load_pos()
        if saved:
            x, y = saved
        else:
            x = geo.right() - w - 60
            y = geo.top() + (geo.height() - h) // 3
        x = max(geo.left(), min(x, geo.right() - w))
        y = max(geo.top(), min(y, geo.bottom() - h))
        self.move(x, y)

    def _clear_prices(self):
        while self._prices_col.count():
            it = self._prices_col.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

    # ---------------------------------------------------------------- slots

    def _on_prices(self, listings: list, trade_url: str):
        self._clear_prices()

        if not listings:
            self._prices_col.addWidget(_lbl('No results', _DIM))
        else:
            for lst in listings:
                row = QHBoxLayout()
                row.setSpacing(8)
                row.addWidget(_lbl(f'{lst.price_amount:g} {lst.price_currency}',
                                   _PRICE, 12, bold=True))
                seller = QLabel(lst.seller)
                seller.setStyleSheet(f'color: {_DIM}; font-size: 10px;')
                seller.setMaximumWidth(130)
                seller.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                row.addWidget(seller)
                row.addStretch()
                row.addWidget(_lbl(lst.age, _DIM, 10))
                w = QWidget()
                w.setLayout(row)
                self._prices_col.addWidget(w)

        self._prices_col.addStretch()

        if trade_url:
            self.trade_url = trade_url
            self._browser_btn.setEnabled(True)

        self.adjustSize()
        if not self._dragged:
            self._place()

    def _open_browser(self):
        if self.trade_url:
            subprocess.Popen(
                ['xdg-open', self.trade_url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,   # detach — no zombie
            )

    # ---------------------------------------------------------------- events

    def closeEvent(self, event):
        # Disconnect signal first so _on_prices doesn't fire on a dead widget
        try:
            self._thread.done.disconnect()
        except Exception:
            pass
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)   # up to 2s, then give up
        self._esc.stop()
        event.accept()
        # Tool windows don't count for quitOnLastWindowClosed — quit explicitly
        QApplication.quit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._dragged = True

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        if self._dragged:
            _save_pos(self.x(), self.y())


_POS_FILE = Path.home() / '.cache' / 'poepricecheckwayland' / 'overlay_pos.json'


def _load_pos() -> tuple[int, int] | None:
    try:
        x, y = json.loads(_POS_FILE.read_text())
        return int(x), int(y)
    except (OSError, ValueError, TypeError):
        return None


def _save_pos(x: int, y: int):
    _POS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _POS_FILE.write_text(json.dumps([x, y]))


# ------------------------------------------------------------------ entry

def run_overlay(item: ParsedItem, db, ninja: NinjaClient,
                trade: TradeClient, cfg):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    stat_filters = []
    if item.rarity in ('Rare', 'Magic') and item.is_identified and item.explicits:
        stat_filters = db.match_all(item.explicits)

    win = OverlayWindow(item, stat_filters, trade, ninja, cfg.max_listings)
    win.show()
    sys.exit(app.exec())
