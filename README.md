<div align="center">

<img src="app_icon.png" width="128" alt="PoEWaylandTrade icon" />

# PoEWaylandTrade

**Path of Exile price checker that actually works on native Wayland**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-KDE%20Plasma%20%7C%20Wayland-6B4FBB?logo=kde)](https://kde.org)
[![PoE](https://img.shields.io/badge/PoE-Steam%20%2F%20Proton-orange)](https://www.pathofexile.com)

*Built by [retampweb](https://github.com/retampweb) with [Claude Sonnet](https://claude.ai) (Anthropic AI)*

</div>

---

## Why this exists

Every popular PoE price checker — Awakened PoE Trade, PathOfPriceCheck — injects keystrokes via **XTest / XDotool**. That only works with X11 windows.

If you run PoE through Steam + Proton with **`PROTON_ENABLE_WAYLAND=1`** (the performance flag), the game becomes a **native Wayland window**. XTest can't touch it. Tools just silently break.

This project solves that with three tricks:
- **evdev hotkey daemon** — reads the keyboard straight from `/dev/input`, so `Ctrl+Alt+D` works in any window, including a fullscreen Wayland game (KDE Plasma 6 no longer ships `khotkeys`)
- **[ydotool](https://github.com/ReimuNotMoe/ydotool)** — injects `Ctrl+C` through `/dev/uinput` at kernel level, bypassing Wayland's security model entirely
- **PyQt6 as XWayland client** — the overlay runs as X11, and KDE Plasma's compositor renders `WindowStaysOnTopHint` X11 windows above native Wayland windows

---

## Features

<table>
<tr>
<td width="50%">

**🔍 Item Price Check**
- Hover over any item → press hotkey → instant overlay
- Uniques, currency, gems, div cards via **poe.ninja** (30 min cache)
- Uniques priced per link count (6L Iron Fortress ≠ unlinked one)
- Rares & magic via **GGG Trade API** — searches the whole item class with mods at ≥85% of your rolls
- Shows all mods, affixes, implicits, item level, sockets

</td>
<td width="50%">

**📦 Stash Valuation**
- Scans all stash tabs via GGG API
- Per-tab value in chaos / divine
- Double-click any tab → per-item breakdown sorted by value
- 5-minute cache, rate-limit safe, ↺ Refresh button

</td>
</tr>
</table>

**Also:** single-instance lock (no overlay stacking), clean thread shutdown on close, hotkey daemon in KDE autostart

---

## Requirements

| Package | Purpose |
|---|---|
| `ydotool` ≥ 1.0 + `ydotoold` | Keystroke injection over Wayland |
| `wl-clipboard` | Read Wayland clipboard (`wl-paste`) |
| Python ≥ 3.11 | Runtime |
| `python-pyqt6` | Overlay GUI |
| `python-requests` | HTTP client |
| `python-evdev` | Global hotkey |
| `input` group membership | Hotkey daemon reads `/dev/input` |

---

## Installation

```bash
git clone https://github.com/retampweb/PoEWaylandTrade.git
cd PoEWaylandTrade
bash install.sh
```

`install.sh` installs packages via `pacman`, enables `ydotoold`, adds you to the `input` group (with a temporary ACL so no re-login is needed right away), and starts the hotkey daemon + adds it to KDE autostart.

> **Arch / CachyOS / Manjaro only** (uses `pacman`). On other distros install the packages manually, then run `python3 shortcut_daemon.py --start`.

The hotkey daemon starts automatically on login. To run it by hand:

```bash
python3 shortcut_daemon.py          # foreground, prints every hotkey press
python3 shortcut_daemon.py --start  # background + autostart entry
```

---

## Configuration

On first run, a config is created at `~/.config/poepricecheckwayland/config.json`:

```json
{
  "league": "",
  "poesessid": "YOUR_SESSION_ID_HERE",
  "account_name": "",
  "max_listings": 6
}
```

| Key | Default | Notes |
|---|---|---|
| `league` | `""` | Auto-detected from GGG API if empty |
| `poesessid` | `""` | Required for stash scan — browser DevTools → Application → Cookies → pathofexile.com |
| `account_name` | `""` | Auto-detected from `poesessid` if empty |
| `max_listings` | `6` | Trade listings shown in overlay |

---

## Usage

### Item Price Check

1. Hover your mouse over an item in Path of Exile
2. Press **`Ctrl+Alt+D`** (or your configured hotkey)
3. Overlay appears near cursor with mods + live prices
4. **Escape** or **✕** to close

```bash
# Run manually
python poecheck.py
```

### Stash Valuation

1. Press **`Ctrl+Alt+S`** (or your configured hotkey)
2. Window shows all tabs with estimated market value
3. Double-click any tab row for per-item breakdown
4. **Escape** or **✕** to close

```bash
# Run manually
python poestash.py
```

---

## How it works

```
Ctrl+Alt+D
  │
  ▼
shortcut_daemon.py ── evdev reads /dev/input, launches:
  │
  ▼
poecheck.py
  ├─ fcntl.flock ──────── already running? exit immediately (no stacking)
  ├─ wait until Ctrl/Alt are physically released
  ├─ ydotool key 29:1 46:1 46:0 29:0 ────► PoE (native Wayland window)
  ├─ wl-paste ◄──────────────────────────── Wayland clipboard
  ├─ parser.py ── split clipboard text into ParsedItem
  ├─ stats_db.py ── mod text → GGG stat IDs (cached 24h)
  ├─ ninja.py / trade.py ── fetch prices in background QThread
  └─ overlay.py ── PyQt6 XWayland window, always-on-top over Wayland game
```

---

## Project structure

```
poecheck.py        entry point — price check
poestash.py        entry point — stash valuation
parser.py          parse PoE clipboard text → ParsedItem
stats_db.py        GGG stats.json cache + mod→stat_id matching
ninja.py           poe.ninja API client
trade.py           GGG Trade API client
overlay.py         item overlay window (PyQt6)
stash.py           GGG stash API + pricing
stash_window.py    stash valuation window (PyQt6)
config.py          config loader with auto-detection
shortcut_daemon.py global hotkey daemon (evdev)
install.sh         one-shot installer (Arch/CachyOS/Manjaro)
```

---

## Troubleshooting

**`ydotool: command not found`**
→ `sudo pacman -S ydotool` and add yourself to the input group: `sudo usermod -aG input $USER`, then re-login

**Hotkey does nothing**
→ Run `python3 shortcut_daemon.py` in a terminal. If it says *no keyboard found*, you're not in the `input` group yet — re-login, or for this session only: `sudo setfacl -m u:$USER:r /dev/input/event*`. Every press is logged to `/tmp/poecheck_debug.log`.

**Hotkey fires but no overlay**
→ Check `/tmp/poecheck_debug.log`. *"no item in clipboard"* means the game didn't receive Ctrl+C — hover the item before pressing, and make sure `ydotoold` is running (`pgrep ydotoold`). Note that ydotool 1.x needs raw keycodes; `ydotool key ctrl+c` is silently ignored.

**Overlay doesn't appear**
→ Make sure `QT_QPA_PLATFORM=xcb` is set and XWayland is enabled in KDE Plasma settings

**Stash scan returns 403**
→ POESESSID expired — get a fresh one and update `~/.config/poepricecheckwayland/config.json`

**Prices stale**
→ poe.ninja data cached 30 min at `~/.cache/poepricecheckwayland/` — delete that folder to force refresh

---

## License

[MIT](LICENSE)

---

<div align="center">

*This project was built in a single session through a collaborative conversation between*
*[retampweb](https://github.com/retampweb) and [Claude Sonnet](https://claude.ai) (Anthropic AI).*

*The entire architecture, all Python files, debugging, and optimization were designed and written*
*together in real time — from the initial "XTest won't work on Wayland" problem to a fully working tool.*

*Feel free to use it, fork it, improve it.* 🎮

</div>
