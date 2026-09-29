"""poe.ninja price lookup — currency, essences, uniques, gems, div cards."""
import json, time
from pathlib import Path
import requests

# Rarities that are priced via poe.ninja instead of the trade API
NINJA_RARITIES = {'Currency', 'Gem', 'Divination Card', 'Unique'}

NINJA_BASE = 'https://poe.ninja/api/data'
CACHE_DIR = Path.home() / '.cache' / 'poepricecheckwayland'
CACHE_TTL = 1800  # 30 min
HEADERS = {'User-Agent': 'poe-price-check-wayland/1.0'}

# (api_type, endpoint)
_CATEGORIES = [
    ('Currency',         'currencyoverview'),
    ('Fragment',         'currencyoverview'),
    ('Essence',          'itemoverview'),
    ('Oil',              'itemoverview'),
    ('Scarab',           'itemoverview'),
    ('Fossil',           'itemoverview'),
    ('Resonator',        'itemoverview'),
    ('DivinationCard',   'itemoverview'),
    ('SkillGem',         'itemoverview'),
    ('UniqueArmour',     'itemoverview'),
    ('UniqueWeapon',     'itemoverview'),
    ('UniqueAccessory',  'itemoverview'),
    ('UniqueFlask',      'itemoverview'),
    ('UniqueJewel',      'itemoverview'),
    ('UniqueMap',        'itemoverview'),
]

# Item rarities that poe.ninja covers
NINJA_RARITIES = {'Currency', 'Gem', 'Divination Card', 'Unique'}


class NinjaClient:
    def __init__(self, league: str):
        self.league = league
        self._cache: dict[str, dict] = {}   # name.lower() → price info
        self._loaded = False

    def get_price(self, name: str) -> dict | None:
        if not self._loaded:
            self._load_all()
        return self._cache.get(name.lower())

    def _load_all(self):
        self._loaded = True
        for cat, endpoint in _CATEGORIES:
            data = self._fetch_cached(endpoint, cat)
            if not data:
                continue
            if endpoint == 'currencyoverview':
                for e in data.get('lines', []):
                    n = e.get('currencyTypeName', '')
                    if n:
                        self._cache[n.lower()] = {
                            'name': n,
                            'chaos_value': e.get('chaosEquivalent', 0),
                            'category': cat,
                        }
            else:
                for e in data.get('lines', []):
                    n = e.get('name', '')
                    if n:
                        self._cache[n.lower()] = {
                            'name': n,
                            'chaos_value': e.get('chaosValue', 0),
                            'divine_value': e.get('divineValue', 0),
                            'category': cat,
                        }

    def _fetch_cached(self, endpoint: str, category: str) -> dict | None:
        safe_league = self.league.replace(' ', '_')
        cache_file = CACHE_DIR / f'{category}_{safe_league}.json'
        if cache_file.exists():
            if time.time() - cache_file.stat().st_mtime < CACHE_TTL:
                try:
                    return json.loads(cache_file.read_text())
                except Exception:
                    pass
        try:
            resp = requests.get(
                f'{NINJA_BASE}/{endpoint}',
                params={'league': self.league, 'type': category},
                headers=HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data))
            return data
        except Exception as e:
            print(f'poe.ninja {category}: {e}')
            return None
