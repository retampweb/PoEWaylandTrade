"""Stash tab scanning — GGG character-window API + poe.ninja pricing."""
import json, re, time
from dataclasses import dataclass, field
from pathlib import Path
import requests

STASH_URL = 'https://www.pathofexile.com/character-window/get-stash-items'
CACHE_DIR = Path.home() / '.cache' / 'poepricecheckwayland' / 'stash'
CACHE_TTL = 300   # 5 minutes per tab
HEADERS = {'User-Agent': 'poe-price-check-wayland/1.0'}

# GGG frameType constants
FT_NORMAL   = 0
FT_MAGIC    = 1
FT_RARE     = 2
FT_UNIQUE   = 3
FT_GEM      = 4
FT_CURRENCY = 5
FT_DIVCARD  = 6

# frameTypes we can price via poe.ninja
_PRICEABLE = {FT_UNIQUE, FT_GEM, FT_CURRENCY, FT_DIVCARD}


def _strip_tags(s: str) -> str:
    return re.sub(r'<<[^>]*>>', '', s).replace('\n', ' ').strip()


@dataclass
class StashItem:
    name: str        # unique name (empty for non-uniques)
    type_line: str   # base type / currency name
    frame_type: int
    stack_size: int = 1
    chaos_value: float = 0.0
    priced: bool = False

    @property
    def display_name(self) -> str:
        return self.name or self.type_line

    @property
    def total_chaos(self) -> float:
        return self.chaos_value * self.stack_size

    @property
    def frame_label(self) -> str:
        return {0: 'Normal', 1: 'Magic', 2: 'Rare', 3: 'Unique',
                4: 'Gem', 5: 'Currency', 6: 'Div Card'}.get(self.frame_type, '?')


@dataclass
class StashTab:
    index: int
    name: str
    tab_type: str
    items: list[StashItem] = field(default_factory=list)

    @property
    def total_chaos(self) -> float:
        return sum(i.total_chaos for i in self.items)

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def priced_count(self) -> int:
        return sum(1 for i in self.items if i.priced)


class StashScanner:
    def __init__(self, account: str, league: str, poesessid: str):
        self.account = account
        self.league = league
        self._s = requests.Session()
        self._s.headers.update(HEADERS)
        if poesessid:
            self._s.cookies.set('POESESSID', poesessid, domain='www.pathofexile.com')
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ public

    def list_tabs(self) -> list[dict]:
        """Return list of all stash tab descriptors (cached 5 min)."""
        cache = CACHE_DIR / f'tabs_{self.account}_{_safe(self.league)}.json'
        if cache.exists() and _fresh(cache):
            return json.loads(cache.read_text())

        data = self._api(0, tabs=True)
        tabs = data.get('tabs', [])
        cache.write_text(json.dumps(tabs))
        return tabs

    def is_tab_cached(self, index: int) -> bool:
        """True if the tab's item data is still fresh in cache."""
        cache = CACHE_DIR / f'items_{self.account}_{_safe(self.league)}_{index}.json'
        return cache.exists() and _fresh(cache)

    def fetch_tab_items(self, index: int) -> list[dict]:
        """Fetch raw item list for one tab (cached 5 min).
        NOTE: rate-limit sleep is the caller's responsibility (ScanThread)."""
        cache = CACHE_DIR / f'items_{self.account}_{_safe(self.league)}_{index}.json'
        if cache.exists() and _fresh(cache):
            return json.loads(cache.read_text())

        data = self._api(index)
        items = data.get('items', [])
        cache.write_text(json.dumps(items))
        return items

    def price_tab(self, tab_info: dict, ninja) -> StashTab:
        """Scan one tab and price its items via poe.ninja."""
        tab = StashTab(
            index=tab_info['i'],
            name=tab_info.get('n', f'Tab {tab_info["i"]}'),
            tab_type=tab_info.get('type', 'NormalStash'),
        )

        for raw in self.fetch_tab_items(tab_info['i']):
            ft = raw.get('frameType', 0)
            item = StashItem(
                name=_strip_tags(raw.get('name', '')),
                type_line=_strip_tags(raw.get('typeLine', '')),
                frame_type=ft,
                stack_size=max(raw.get('stackSize', 1) or 1, 1),
            )

            # poe.ninja lookup
            lookup = item.name if ft == FT_UNIQUE else item.type_line
            if not lookup:
                lookup = item.type_line or item.name

            price = ninja.get_price(lookup)
            if not price and ft == FT_CURRENCY:
                # fallback: try name (some essences have name set)
                price = ninja.get_price(item.name)

            if price:
                item.chaos_value = price.get('chaos_value', 0)
                item.priced = bool(item.chaos_value)

            tab.items.append(item)

        return tab

    def invalidate_cache(self):
        """Delete all cached stash data (force re-fetch)."""
        for f in CACHE_DIR.glob(f'*_{self.account}_*.json'):
            f.unlink(missing_ok=True)

    # ----------------------------------------------------------------- private

    def _api(self, index: int, tabs: bool = False) -> dict:
        params: dict = {
            'accountName': self.account,
            'league': self.league,
            'tabIndex': index,
        }
        if tabs:
            params['tabs'] = '1'
        resp = self._s.get(STASH_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()


# -------------------------------------------------------------------- helpers

def _safe(s: str) -> str:
    return re.sub(r'[^\w]', '_', s)


def _fresh(path: Path) -> bool:
    return (time.time() - path.stat().st_mtime) < CACHE_TTL
