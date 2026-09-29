"""
Maps PoE item mod text → GGG trade stat IDs.
Fetches once per day from https://www.pathofexile.com/api/trade/data/stats
"""
import re, json, time
from pathlib import Path
import requests

STATS_URL = 'https://www.pathofexile.com/api/trade/data/stats'
CACHE_FILE = Path.home() / '.config' / 'poepricecheckwayland' / 'stats.json'
CACHE_TTL = 86400  # 24h
HEADERS = {'User-Agent': 'poe-price-check-wayland/1.0'}

# Only use these stat groups for explicit mod matching
_WANTED_GROUPS = {'explicit', 'fractured', 'implicit', 'pseudo'}


def _normalize(text: str) -> str:
    """Replace numbers with # to create a matchable template."""
    return re.sub(r'\d+(?:\.\d+)?', '#', text).strip()


def _extract_value(text: str) -> float:
    """Extract the first numeric value from mod text."""
    m = re.search(r'\d+(?:\.\d+)?', text)
    return float(m.group()) if m else 0.0


class StatsDB:
    def __init__(self, entries: list[dict]):
        # lookup: normalized_text → list of (stat_id, group)
        # We keep explicit ones first for priority
        self._lookup: dict[str, list[tuple[str, str]]] = {}
        for e in entries:
            norm = _normalize(e.get('text', ''))
            if not norm:
                continue
            stat_id = e.get('id', '')
            group = stat_id.split('.')[0] if '.' in stat_id else ''
            if norm not in self._lookup:
                self._lookup[norm] = []
            # Insert explicits at the front
            if group == 'explicit':
                self._lookup[norm].insert(0, (stat_id, group))
            else:
                self._lookup[norm].append((stat_id, group))

    def match(self, mod_text: str) -> tuple[str, float] | None:
        """
        Match a mod string from clipboard to a trade stat ID.
        Returns (stat_id, value) or None.
        """
        norm = _normalize(mod_text)
        matches = self._lookup.get(norm)
        if not matches:
            return None
        stat_id = matches[0][0]
        value = _extract_value(mod_text)
        return stat_id, value

    def match_all(self, mods: list[str]) -> list[dict]:
        """
        Match a list of mod strings.
        Returns list of trade API filter dicts (only matched ones).
        """
        results = []
        for mod in mods:
            m = self.match(mod)
            if m:
                stat_id, value = m
                # exact values almost never match anything; 85% is what APT uses
                entry = {'id': stat_id, 'disabled': False}
                if value is not None:
                    entry['value'] = {'min': int(value * 0.85)}
                results.append(entry)
        return results

    @classmethod
    def get(cls) -> 'StatsDB':
        if CACHE_FILE.exists():
            age = time.time() - CACHE_FILE.stat().st_mtime
            if age < CACHE_TTL:
                try:
                    data = json.loads(CACHE_FILE.read_text())
                    return cls(_flatten(data))
                except Exception:
                    pass

        try:
            print('Fetching stats database from GGG...')
            resp = requests.get(STATS_URL, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(json.dumps(data))
            return cls(_flatten(data))
        except Exception as e:
            print(f'Could not fetch stats DB: {e}')
            return cls([])


def _flatten(data: dict) -> list[dict]:
    entries = []
    for group in data.get('result', []):
        gid = group.get('id', '')
        if gid not in _WANTED_GROUPS:
            continue
        for entry in group.get('entries', []):
            entries.append(entry)
    return entries
