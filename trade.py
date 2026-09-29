"""GGG official trade API — search + fetch listings."""
import requests
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote
from typing import Optional

TRADE_BASE = 'https://www.pathofexile.com/api/trade'
HEADERS = {
    'User-Agent': 'poe-price-check-wayland/1.0',
    'Content-Type': 'application/json',
}

# PoE "Item Class:" → trade API category
_CATEGORY = {
    'Rings': 'accessory.ring', 'Amulets': 'accessory.amulet', 'Belts': 'accessory.belt',
    'Body Armours': 'armour.chest', 'Helmets': 'armour.helmet', 'Gloves': 'armour.gloves',
    'Boots': 'armour.boots', 'Shields': 'armour.shield', 'Quivers': 'armour.quiver',
    'Jewels': 'jewel.base', 'Abyss Jewels': 'jewel.abyss',
    'One Hand Swords': 'weapon.onesword', 'Thrusting One Hand Swords': 'weapon.onesword',
    'Two Hand Swords': 'weapon.twosword', 'One Hand Axes': 'weapon.oneaxe',
    'Two Hand Axes': 'weapon.twoaxe', 'One Hand Maces': 'weapon.onemace',
    'Two Hand Maces': 'weapon.twomace', 'Sceptres': 'weapon.sceptre',
    'Daggers': 'weapon.dagger', 'Rune Daggers': 'weapon.runedagger',
    'Claws': 'weapon.claw', 'Bows': 'weapon.bow', 'Staves': 'weapon.staff',
    'Warstaves': 'weapon.warstaff', 'Wands': 'weapon.wand',
}


@dataclass
class Listing:
    price_amount: float
    price_currency: str
    seller: str
    age: str
    whisper: str = ''


class TradeClient:
    def __init__(self, league: str, poesessid: str = ''):
        self.league = league
        self._s = requests.Session()
        self._s.headers.update(HEADERS)
        if poesessid:
            self._s.cookies.set('POESESSID', poesessid, domain='www.pathofexile.com')

    # ------------------------------------------------------------------ public

    def search_and_fetch(
        self,
        item,   # ParsedItem
        stat_filters: list[dict],
        max_listings: int = 6,
    ) -> tuple[list[Listing], str]:
        """
        Search trade and return (listings, trade_url).
        Returns ([], '') on any error.
        """
        try:
            body = self._build_query(item, stat_filters)
            query_id, result_ids = self._search(body)
            listings = self._fetch(query_id, result_ids[:max_listings])
            url = self.trade_url(query_id)
            return listings, url
        except Exception as e:
            print(f'Trade API error: {e}')
            return [], ''

    def trade_url(self, query_id: str) -> str:
        return f'https://www.pathofexile.com/trade/search/{quote(self.league)}/{query_id}'

    # ----------------------------------------------------------------- private

    def _build_query(self, item, stat_filters: list[dict]) -> dict:
        query: dict = {'status': {'option': 'online'}}

        filters: dict = {}
        category = _CATEGORY.get(item.item_class)

        if item.rarity == 'Unique':
            query['name'] = item.name
            query['type'] = item.base_type
        elif item.rarity in ('Rare', 'Magic') and category:
            # search the whole class (any ring), not just this exact base
            filters['type_filters'] = {'filters': {'category': {'option': category}}}
        else:
            query['type'] = item.base_type

        query['stats'] = [{'type': 'and', 'filters': stat_filters}]

        if item.is_corrupted:
            filters['misc_filters'] = {'filters': {'corrupted': {'option': 'true'}}}
        if item.links >= 5:
            filters['socket_filters'] = {'filters': {'links': {'min': item.links}}}
        if filters:
            query['filters'] = filters

        return {'query': query, 'sort': {'price': 'asc'}}

    def _search(self, body: dict) -> tuple[str, list[str]]:
        url = f'{TRADE_BASE}/search/{quote(self.league)}'
        resp = self._s.post(url, json=body, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        return data['id'], data.get('result', [])

    def _fetch(self, query_id: str, result_ids: list[str]) -> list[Listing]:
        if not result_ids:
            return []
        ids_str = ','.join(result_ids)
        url = f'{TRADE_BASE}/fetch/{ids_str}?query={query_id}'
        resp = self._s.get(url, timeout=12)
        resp.raise_for_status()

        listings = []
        for r in resp.json().get('result', []):
            lst = r.get('listing', {})
            price = lst.get('price', {})
            account = lst.get('account', {})
            listings.append(Listing(
                price_amount=price.get('amount', 0),
                price_currency=price.get('currency', '?'),
                seller=account.get('name', '?'),
                age=_age(lst.get('indexed', '')),
                whisper=lst.get('whisper', ''),
            ))
        return listings


def _age(indexed: str) -> str:
    if not indexed:
        return '?'
    try:
        dt = datetime.fromisoformat(indexed.replace('Z', '+00:00'))
        s = int((datetime.now(timezone.utc) - dt).total_seconds())
        if s < 60:    return f'{s}s'
        if s < 3600:  return f'{s // 60}m'
        if s < 86400: return f'{s // 3600}h'
        return f'{s // 86400}d'
    except Exception:
        return '?'
