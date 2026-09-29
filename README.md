# PoE Price Check — Wayland ❤️

A **native Wayland** Path of Exile 1 price checker for **KDE Plasma** (and any Wayland compositor).  
Works when `PROTON_ENABLE_WAYLAND=1` is set — the case where every X11-based tool like Awakened PoE Trade breaks.

> Built with ❤️ by [retampweb](https://github.com/retampweb) with the help of **Claude Sonnet** (Anthropic AI).  
> Free to use and modify. Contributions welcome.

![icon](app_icon.png)

---

## Why this exists

Most PoE price checkers (Awakened PoE Trade, PathOfPriceCheck, etc.) inject keystrokes via **XTest / XDotool**, which only works with X11 windows.  
When you run PoE through Steam/Proton with `PROTON_ENABLE_WAYLAND=1`, the game becomes a **native Wayland window** — XTest can't touch it.

This tool uses:
- **ydotool** — sends input through `/dev/uinput` at the kernel level, bypassing Wayland's security model
- **PyQt6 as XWayland client** — the overlay window is X11-based, but KDE Plasma compositor renders `WindowStaysOnTopHint` X11 windows above native Wayland windows
- **wl-paste** — reads the Wayland clipboard directly

---

## Features

- **Item price check** — hover over any item, press hotkey → overlay with mods, affixes, price listings
  - Uniques, currency, gems, essences, div cards → **poe.ninja** (instant, cached 30 min)
  - Rares & magic → **GGG Trade API** (live search with stat filters)
- **Stash valuation** — scan all stash tabs, show per-tab and total value in chaos/divine
  - Caches tab data for 5 minutes, rate-limit safe
  - Double-click any tab for per-item breakdown sorted by value
- **Single-instance lock** — pressing hotkey while overlay is open does nothing (no stacking)
- **Clean exit** — all background threads are stopped before process exits
- **Auto KDE shortcuts** setup via `setup_shortcuts.py`

---

## Requirements

| Package | Purpose |
|---|---|
| `ydotool` + `ydotoold` | Keystroke injection over Wayland |
| `wl-clipboard` | Read Wayland clipboard (`wl-paste`) |
| `python` ≥ 3.11 | Runtime |
| `PyQt6` | Overlay GUI |
| `requests` | HTTP (poe.ninja, GGG trade API) |

---

## Installation

```bash
cd /path/to/poepricecheckwayland
bash install.sh
```

`install.sh` will:
1. Install system packages via `pacman` (ydotool, wl-clipboard, python-pyqt6)
2. Enable and start `ydotoold` systemd user service
3. `pip install` Python dependencies
4. Run `setup_shortcuts.py` to register KDE global shortcuts automatically

> **Arch / CachyOS / Manjaro only** (uses `pacman`). On other distros install packages manually.

---

## Configuration

Config is stored in `~/.config/poepricecheckwayland/config.json` (created on first run, **never committed to git**).

```json
{
  "league": "",
  "poesessid": "YOUR_SESSION_ID_HERE",
  "account_name": "",
  "inject_delay_ms": 200,
  "max_listings": 6
}
```

| Key | Default | Notes |
|---|---|---|
| `league` | `""` | Auto-detected from GGG API if empty |
| `poesessid` | `""` | Required for stash scan. Get from browser DevTools → Application → Cookies → pathofexile.com |
| `account_name` | `""` | Auto-detected from `poesessid` if empty |
| `inject_delay_ms` | `200` | Delay after Ctrl+C injection before reading clipboard |
| `max_listings` | `6` | Max trade listings shown in overlay |

---

## Usage

### Price Check (single item)

1. **Hover your mouse over an item** in Path of Exile
2. Press your hotkey (default: `Ctrl+Alt+D`)
3. An overlay appears near your cursor with item mods and price listings
4. Press **Escape** or click **✕** to close

**To run manually:**
```bash
python /path/to/poepricecheckwayland/poecheck.py
```

### Stash Valuation

1. Press your stash hotkey (default: `Ctrl+Alt+S`)
2. A window appears showing all stash tabs with their estimated values
3. Double-click any tab row for a per-item breakdown
4. Click **↺ Refresh** to force re-scan (bypasses cache)
5. Press **Escape** or click **✕** to close

**To run manually:**
```bash
python /path/to/poepricecheckwayland/poestash.py
```

### Closing

- **Escape key** — closes overlay / stash window
- **✕ button** — closes overlay / stash window
- Both methods cleanly stop all background threads before exit

---

## How it works

```
Hotkey pressed
    │
    ▼
poecheck.py
    │
    ├─ Single-instance lock (fcntl.flock) — exits immediately if already running
    │
    ├─ ydotool key ctrl+c  ─────────────────────► PoE (native Wayland window)
    │                                                  copies item to clipboard
    │
    ├─ wl-paste ◄──────────────────────────────── Wayland clipboard
    │
    ├─ parser.py — parse item text into structured ParsedItem
    │
    ├─ stats_db.py — match mods → GGG stat IDs (cached 24h)
    │
    ├─ ninja.py / trade.py — fetch prices (parallel, in QThread)
    │
    └─ overlay.py — PyQt6 XWayland window (always-on-top over Wayland game)
```

---

## Project structure

```
poecheck.py        — entry point: inject Ctrl+C, read clipboard, show overlay
poestash.py        — entry point: launch stash valuation window
parser.py          — parse PoE clipboard text into ParsedItem dataclass
stats_db.py        — download & cache GGG stats.json, match mod text → stat IDs
ninja.py           — poe.ninja API client (currency, uniques, gems, div cards)
trade.py           — GGG Trade API client (rare/magic items)
overlay.py         — PyQt6 item overlay window
stash.py           — GGG stash API client + per-item pricing
stash_window.py    — PyQt6 stash valuation window
config.py          — config file loader with auto-detection
setup_shortcuts.py — KDE global shortcut auto-registration
install.sh         — one-shot installer (Arch/CachyOS/Manjaro)
```

---

## Troubleshooting

**"ydotool not found"**  
→ `sudo pacman -S ydotool` and make sure you're in the `input` group: `sudo usermod -aG input $USER` then re-login.

**"ydotoold not running"**  
→ `systemctl --user start ydotoold` or run `ydotoold &` in a terminal.

**Overlay doesn't appear**  
→ Check `QT_QPA_PLATFORM=xcb` is set. The overlay runs as XWayland; make sure XWayland is enabled in KDE Plasma.

**Stash scan fails with 403**  
→ Your `POESESSID` is expired. Get a fresh one from browser DevTools and update `~/.config/poepricecheckwayland/config.json`.

**Prices not updating**  
→ poe.ninja data is cached for 30 min in `~/.cache/poepricecheckwayland/`. Delete that folder to force refresh.

---

## License

MIT — do whatever you want with it.

---

*Built by retampweb × Claude Sonnet (Anthropic) — because Awakened PoE Trade wouldn't run on Wayland.*
