"""poe.ninja price lookup — currency, essences, uniques, gems, div cards."""
import json, time
from pathlib import Path
import requests

# Rarities that are priced via poe.ninja instead of the trade API
NINJA_RARITIES = {'Currency', 'Gem', 'Divination Card', 'Unique'}

NINJA_BASE = 'https://poe.ninja/poe1/api/economy'
CACHE_DIR = Path.home() / '.cache' / 'poepricecheckwayland'
CACHE_TTL = 1800  # 30 min
HEADERS = {'User-Agent': 'poe-price-check-wayland/1.0'}

# Bulk-traded items live on the currency exchange, the rest on stash listings
_EXCHANGE = ['Currency', 'Fragment', 'Essence', 'Oil', 'Scarab', 'Fossil',
             'Resonator', 'DivinationCard']
_STASH = ['SkillGem', 'UniqueArmour', 'UniqueWeapon', 'UniqueAccessory',
          'UniqueFlask', 'UniqueJewel', 'UniqueMap']


class NinjaClient:
    def __init__(self, league: str):
        self.league = league
        self._cache: dict[str, list[dict]] = {}   # name.lower() → variants
        self._loaded = False

    def get_price(self, name: str, links: int = 0) -> dict | None:
        if not self._loaded:
            self._load_all()
        variants = self._cache.get(name.lower())
        if not variants:
            return None
        want = links if links >= 5 else None
        exact = [v for v in variants if v['links'] == want and not v['variant']]
        return min(exact or variants, key=lambda v: v['chaos_value'])

    def _add(self, name: str, info: dict):
        self._cache.setdefault(name.lower(), []).append({'name': name, **info})

    def _load_all(self):
        self._loaded = True
        for cat in _EXCHANGE:
            data = self._fetch_cached('exchange/current/overview', cat)
            if not data:
                continue
            core = data.get('core', {})
            div_rate = core.get('rates', {}).get('divine', 0)
            names = {i['id']: i['name'] for i in data.get('items', [])}
            for line in data.get('lines', []):
                name = names.get(line.get('id'))
                chaos = line.get('primaryValue', 0)
                if name and chaos:
                    self._add(name, {
                        'chaos_value': chaos,
                        'divine_value': chaos * div_rate,
                        'links': None, 'variant': None, 'category': cat,
                    })
        for cat in _STASH:
            data = self._fetch_cached('stash/current/item/overview', cat)
            if not data:
                continue
            for line in data.get('lines', []):
                name = line.get('name')
                if name:
                    self._add(name, {
                        'chaos_value': line.get('chaosValue', 0),
                        'divine_value': line.get('divineValue', 0),
                        'links': line.get('links'),
                        'variant': line.get('variant'),
                        'category': cat,
                    })

    def _fetch_cached(self, endpoint: str, category: str) -> dict | None:
        safe_league = self.league.replace(' ', '_')
        cache_file = CACHE_DIR / f'ninja_{category}_{safe_league}.json'
        if cache_file.exists() and time.time() - cache_file.stat().st_mtime < CACHE_TTL:
            try:
                return json.loads(cache_file.read_text())
            except ValueError:
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
