"""Stash valuation window — live scan with per-tab breakdown."""
import os, sys
os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QAbstractItemView, QProgressBar, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from stash import StashScanner, StashTab
from ninja import NinjaClient

# ------------------------------------------------------------------ palette
_BG      = '#0d0d0d'
_PANEL   = '#111111'
_BORDER  = '#3a2a1a'
_TEXT    = '#c8b998'
_DIM     = '#665544'
_PRICE   = '#ddcc88'
_GOOD    = '#88bb66'
_HEAD    = '#af6025'
_RED     = '#ff4444'
_UNIQUE  = '#af6025'
_CURRENCY= '#aa9e82'
_GEM     = '#1ba29b'
_DIVCARD = '#c8c8aa'

_STYLE = f"""
QWidget {{ background: {_BG}; color: {_TEXT}; font-size: 11px; }}
QLabel  {{ background: transparent; }}
QTableWidget {{
    background: {_PANEL}; color: {_TEXT};
    gridline-color: {_BORDER};
    selection-background-color: #2a1a0a;
    border: 1px solid {_BORDER};
}}
QHeaderView::section {{
    background: #1a1208; color: {_HEAD};
    border: 1px solid {_BORDER};
    padding: 3px 6px;
    font-size: 11px;
}}
QPushButton {{
    background: #221a10; border: 1px solid {_BORDER};
    color: {_TEXT}; padding: 3px 10px; border-radius: 2px;
}}
QPushButton:hover  {{ background: #332a18; border-color: #665544; }}
QPushButton:disabled {{ color: #443322; border-color: #221a10; }}
QProgressBar {{
    background: #1a1208; border: 1px solid {_BORDER};
    color: {_TEXT}; text-align: center; border-radius: 2px;
}}
QProgressBar::chunk {{ background: #554422; border-radius: 2px; }}
"""

_FRAME_COLOR = {
    3: _UNIQUE, 4: _GEM, 5: _CURRENCY, 6: _DIVCARD,
}


def _cell(text: str, color: str = _TEXT, align=Qt.AlignmentFlag.AlignLeft,
          bold: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    item.setForeground(QColor(color))
    item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _fmt_div(chaos: float, div_rate: float) -> str:
    if div_rate <= 0:
        return f'{chaos:.0f}c'
    d = chaos / div_rate
    if d >= 1:
        return f'{d:.2f} div'
    return f'{chaos:.0f}c'


# ------------------------------------------------------------------ worker

class ScanThread(QThread):
    tab_done  = pyqtSignal(object)    # StashTab
    all_done  = pyqtSignal()
    error     = pyqtSignal(str)
    progress  = pyqtSignal(int, int)  # current, total

    def __init__(self, scanner: StashScanner, ninja: NinjaClient):
        super().__init__()
        self.scanner = scanner
        self.ninja   = ninja
        self._abort  = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            tabs = self.scanner.list_tabs()
            self.progress.emit(0, len(tabs))
            for i, tab_info in enumerate(tabs):
                if self._abort:
                    return
                # Rate-limit: 1.2 s before each real API call, in 100 ms chunks
                # so abort() takes effect within 100 ms instead of 1.2 s
                if not self.scanner.is_tab_cached(tab_info['i']):
                    for _ in range(12):
                        if self._abort:
                            return
                        self.msleep(100)
                tab = self.scanner.price_tab(tab_info, self.ninja)
                self.tab_done.emit(tab)
                self.progress.emit(i + 1, len(tabs))
            self.all_done.emit()
        except Exception as e:
            self.error.emit(str(e))


# ------------------------------------------------------------------ detail dialog

class TabDetailDialog(QDialog):
    def __init__(self, tab: StashTab, div_rate: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'{tab.name} — {len(tab.items)} items')
        self.setStyleSheet(_STYLE)
        self.setMinimumSize(620, 420)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        tbl = QTableWidget(0, 4)
        tbl.setHorizontalHeaderLabels(['Item', 'Type', 'Stack', 'Value'])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.setSortingEnabled(True)
        layout.addWidget(tbl)

        # Sort by value descending
        priced = [i for i in tab.items if i.priced]
        unpriced = [i for i in tab.items if not i.priced]
        sorted_items = sorted(priced, key=lambda x: x.total_chaos, reverse=True) + unpriced

        for item in sorted_items:
            row = tbl.rowCount()
            tbl.insertRow(row)
            color = _FRAME_COLOR.get(item.frame_type, _TEXT)
            tbl.setItem(row, 0, _cell(item.display_name, color))
            tbl.setItem(row, 1, _cell(item.frame_label, _DIM))
            tbl.setItem(row, 2, _cell(item.stack_size,
                                      align=Qt.AlignmentFlag.AlignRight))
            val_text = _fmt_div(item.total_chaos, div_rate) if item.priced else '?'
            tbl.setItem(row, 3, _cell(val_text, _PRICE if item.priced else _DIM,
                                      align=Qt.AlignmentFlag.AlignRight))

        tbl.resizeRowsToContents()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close = QPushButton('Close')
        close.clicked.connect(self.accept)
        btn_row.addWidget(close)
        layout.addLayout(btn_row)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.accept()


# ------------------------------------------------------------------ main window

class StashWindow(QWidget):
    def __init__(self, scanner: StashScanner, ninja: NinjaClient, league: str):
        super().__init__()
        self.scanner  = scanner
        self.ninja    = ninja
        self.league   = league
        self._tabs: list[StashTab] = []
        self._thread: ScanThread | None = None
        self._div_rate = 0.0
        self._drag_pos = None

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setStyleSheet(_STYLE)
        self.setMinimumSize(640, 420)

        self._build()
        self._start_scan()

    # ---------------------------------------------------------------- layout

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(6)

        # Title bar
        title_row = QHBoxLayout()
        self._title_lbl = QLabel(f'Stash Scan — {self.league}')
        self._title_lbl.setStyleSheet(f'color: {_HEAD}; font-size: 14px; font-weight: bold;')
        title_row.addWidget(self._title_lbl)
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

        # Progress
        self._progress = QProgressBar()
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        root.addWidget(self._progress)

        self._status_lbl = QLabel('Starting scan…')
        self._status_lbl.setStyleSheet(f'color: {_DIM}; font-size: 10px;')
        root.addWidget(self._status_lbl)

        # Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(['Tab', 'Items', 'Priced', 'Value'])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.cellDoubleClicked.connect(self._on_row_dclick)
        root.addWidget(self._table)

        # Total row
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f'color: {_BORDER};')
        root.addWidget(sep)

        total_row = QHBoxLayout()
        total_row.addWidget(QLabel('Total:'))
        self._total_lbl = QLabel('—')
        self._total_lbl.setStyleSheet(
            f'color: {_PRICE}; font-size: 14px; font-weight: bold;'
        )
        total_row.addWidget(self._total_lbl)
        total_row.addStretch()

        self._cache_lbl = QLabel('')
        self._cache_lbl.setStyleSheet(f'color: {_DIM}; font-size: 10px;')
        total_row.addWidget(self._cache_lbl)

        self._refresh_btn = QPushButton('↺ Refresh')
        self._refresh_btn.clicked.connect(self._on_refresh)
        total_row.addWidget(self._refresh_btn)

        root.addLayout(total_row)

    # ---------------------------------------------------------------- scan

    def _start_scan(self):
        self._tabs.clear()
        self._table.setRowCount(0)
        self._total_lbl.setText('—')
        self._refresh_btn.setEnabled(False)
        self._progress.setValue(0)

        # Get divine rate for display
        div_price = self.ninja.get_price('Divine Orb')
        self._div_rate = div_price.get('chaos_value', 0) if div_price else 0

        self._thread = ScanThread(self.scanner, self.ninja)
        self._thread.tab_done.connect(self._on_tab)
        self._thread.all_done.connect(self._on_done)
        self._thread.error.connect(self._on_error)
        self._thread.progress.connect(self._on_progress)
        self._thread.start()

    def _on_progress(self, current: int, total: int):
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._status_lbl.setText(f'Scanning… ({current}/{total})')

    def _on_tab(self, tab: StashTab):
        self._tabs.append(tab)
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, _cell(tab.name, _TEXT))
        self._table.setItem(row, 1, _cell(tab.item_count,
                                          align=Qt.AlignmentFlag.AlignRight))
        self._table.setItem(row, 2, _cell(tab.priced_count,
                                          align=Qt.AlignmentFlag.AlignRight,
                                          color=_GOOD if tab.priced_count > 0 else _DIM))
        val = _fmt_div(tab.total_chaos, self._div_rate) if tab.total_chaos > 0 else '—'
        self._table.setItem(row, 3, _cell(val, _PRICE if tab.total_chaos > 0 else _DIM,
                                          align=Qt.AlignmentFlag.AlignRight))
        self._table.resizeRowsToContents()
        self._update_total()

    def _on_done(self):
        self._status_lbl.setText('Scan complete  (double-click a tab for details)')
        self._refresh_btn.setEnabled(True)
        self._progress.setValue(self._progress.maximum())
        self._cache_lbl.setText('cached 0m')

    def _on_error(self, msg: str):
        self._status_lbl.setText(f'Error: {msg}')
        self._refresh_btn.setEnabled(True)

    def _update_total(self):
        total = sum(t.total_chaos for t in self._tabs)
        self._total_lbl.setText(_fmt_div(total, self._div_rate))

    def _on_row_dclick(self, row: int, _col: int):
        if row < len(self._tabs):
            dlg = TabDetailDialog(self._tabs[row], self._div_rate, self)
            dlg.exec()

    def _on_refresh(self):
        if self._thread and self._thread.isRunning():
            self._thread.abort()
            self._thread.wait(3000)  # max 3s wait (abort fires within 100ms of next chunk)
        self.scanner.invalidate_cache()
        self._start_scan()

    def _stop_thread(self):
        """Cleanly stop the scan thread if running."""
        if self._thread and self._thread.isRunning():
            self._thread.abort()
            self._thread.quit()
            self._thread.wait(3000)

    # ---------------------------------------------------------------- events

    def closeEvent(self, event):
        self._stop_thread()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()  # closeEvent handles thread cleanup

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


# ------------------------------------------------------------------ entry

def run_stash_window(scanner: StashScanner, ninja: NinjaClient,
                     league: str):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    win = StashWindow(scanner, ninja, league)

    # Center on screen
    screen = QApplication.primaryScreen().geometry()
    win.move(
        (screen.width()  - win.minimumWidth())  // 2,
        (screen.height() - win.minimumHeight()) // 2,
    )
    win.show()
    sys.exit(app.exec())
