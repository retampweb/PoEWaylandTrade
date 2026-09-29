import json, requests
from pathlib import Path
from dataclasses import dataclass, asdict

CONFIG_DIR = Path.home() / '.config' / 'poepricecheckwayland'
CONFIG_FILE = CONFIG_DIR / 'config.json'

HEADERS = {'User-Agent': 'poe-price-check-wayland/1.0'}

DEFAULTS = {
    'league': '',        # empty = auto-detect
    'poesessid': '',
    'account_name': '',  # empty = auto-detect from poesessid
    'max_listings': 6,
}


@dataclass
class Config:
    league: str
    poesessid: str
    account_name: str
    max_listings: int

    @classmethod
    def load(cls) -> 'Config':
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            data = {**DEFAULTS, **json.loads(CONFIG_FILE.read_text())}
        else:
            data = DEFAULTS.copy()
            CONFIG_FILE.write_text(json.dumps(data, indent=2))
            print(f'Created config: {CONFIG_FILE}')

        if not data['league']:
            data['league'] = _detect_league()

        if not data['account_name'] and data['poesessid']:
            data['account_name'] = _detect_account(data['poesessid'])

        CONFIG_FILE.write_text(json.dumps(data, indent=2))
        return cls(**{k: data[k] for k in DEFAULTS})


def _detect_account(poesessid: str) -> str:
    try:
        resp = requests.get(
            'https://www.pathofexile.com/api/profile',
            cookies={'POESESSID': poesessid}, headers=HEADERS, timeout=8,
        )
        resp.raise_for_status()
        name = resp.json().get('name', '')
        if name:
            print(f'Auto-detected account: {name}')
        return name
    except Exception as e:
        print(f'Account detection failed: {e}')
    return ''


def _detect_league() -> str:
    try:
        resp = requests.get(
            'https://www.pathofexile.com/api/trade/data/leagues',
            headers=HEADERS, timeout=8
        )
        resp.raise_for_status()
        leagues = resp.json().get('result', [])
        skip = {'Standard', 'Hardcore', 'SSF Standard', 'SSF Hardcore'}
        for league in leagues:
            name = league.get('id', '')
            if name not in skip and 'SSF' not in name and 'Hardcore' not in name:
                print(f'Auto-detected league: {name}')
                return name
    except Exception as e:
        print(f'League detection failed: {e}')
    return 'Standard'
