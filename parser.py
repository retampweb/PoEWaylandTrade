import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedItem:
    rarity: str = ''
    item_class: str = ''
    name: str = ''        # unique/rare name, or item name
    base_type: str = ''     # base type line
    item_level: int = 0
    quality: int = 0
    is_corrupted: bool = False
    is_identified: bool = True
    is_mirrored: bool = False
    is_fractured: bool = False
    implicits: list = field(default_factory=list)
    explicits: list = field(default_factory=list)
    sockets: str = ''
    links: int = 0
    influences: list = field(default_factory=list)
    raw_text: str = ''

    @property
    def display_name(self) -> str:
        return self.name or self.base_type


def _count_links(sockets: str) -> int:
    if not sockets:
        return 0
    return max((g.count('-') + 1 for g in sockets.split()), default=0)


_PROP_PREFIX = re.compile(
    r'^(Quality|Armour|Energy Shield|Evasion|Ward|Physical Damage|Cold Damage|'
    r'Fire Damage|Lightning Damage|Elemental Damage|Chaos Damage|'
    r'Critical Strike Chance|Critical Strike Multiplier|Attacks per Second|'
    r'Weapon Range|Level|Mana|Life|Intelligence|Strength|Dexterity|'
    r'Radius|Stack Size|Experience|Map Tier|Item Quantity|Item Rarity|'
    r'Monster Pack Size|Requirements)'
)

_FLAVOR_PREFIX = re.compile(
    r'^(Right click|Shift click|Can only|Place into|This item|'
    r'Currently has|Reforges|Allocates|Travel to|Adds this|\()'
)


def _is_mod_line(line: str) -> bool:
    if not line or len(line) < 3:
        return False
    if _PROP_PREFIX.match(line):
        return False
    if _FLAVOR_PREFIX.match(line):
        return False
    if line.startswith('"'):
        return False
    return True


def _clean_mod(line: str) -> str:
    line = re.sub(r'\s*\((augmented|crafted|fractured|implicit|enchant)\)', '', line)
    line = re.sub(r'\{[^}]+\}\s*', '', line)
    return line.strip()


_INFLUENCE_TAGS = {
    'Shaper Item': 'Shaper',
    'Elder Item': 'Elder',
    'Crusader Item': 'Crusader',
    'Hunter Item': 'Hunter',
    'Redeemer Item': 'Redeemer',
    'Warlord Item': 'Warlord',
    'Eater of Worlds Item': 'Eater',
    'Searing Exarch Item': 'Exarch',
}


def parse_item(text: str) -> Optional[ParsedItem]:
    item = ParsedItem(raw_text=text)
    sections = [s.strip() for s in text.strip().split('--------') if s.strip()]
    if not sections:
        return None

    # --- Header section ---
    header = [l.strip() for l in sections[0].splitlines() if l.strip()]
    # Current PoE prepends "Item Class: ..." before the Rarity line
    while header and not header[0].startswith('Rarity:'):
        m = re.match(r'Item Class:\s+(.+)', header.pop(0))
        if m:
            item.item_class = m.group(1).strip()
    if not header:
        return None

    m = re.match(r'Rarity:\s+(.+)', header[0])
    if not m:
        return None
    item.rarity = m.group(1).strip()

    if item.rarity in ('Unique', 'Rare'):
        item.name = header[1].strip() if len(header) > 1 else ''
        item.base_type = header[2].strip() if len(header) > 2 else item.name
    elif item.rarity == 'Magic':
        item.name = header[1].strip() if len(header) > 1 else ''
        item.base_type = item.name  # base embedded in magic name
    else:
        # Normal, Currency, Gem, Divination Card
        item.name = header[1].strip() if len(header) > 1 else ''
        item.base_type = header[2].strip() if len(header) > 2 else item.name

    # --- Remaining sections ---
    ilvl_seen = False
    mod_sections: list[list[str]] = []

    for sec in sections[1:]:
        lines = [l.strip() for l in sec.splitlines() if l.strip()]
        if not lines:
            continue

        joined = '\n'.join(lines)
        first = lines[0]

        # Item level
        m = re.match(r'Item Level:\s*(\d+)', first)
        if m:
            item.item_level = int(m.group(1))
            ilvl_seen = True
            continue

        # Sockets
        m = re.match(r'Sockets:\s*(.+)', first)
        if m:
            item.sockets = m.group(1).strip()
            item.links = _count_links(item.sockets)
            continue

        # Simple flag sections
        if joined == 'Corrupted':
            item.is_corrupted = True
            continue
        if joined == 'Unidentified':
            item.is_identified = False
            continue
        if joined == 'Mirrored':
            item.is_mirrored = True
            continue
        if 'Fractured Item' in joined and len(lines) == 1:
            item.is_fractured = True
            continue

        # Note
        if first.startswith('Note:'):
            continue

        # Influences
        for tag, infl in _INFLUENCE_TAGS.items():
            if tag in joined:
                item.influences.append(infl)

        # Quality from property sections
        for l in lines:
            qm = re.match(r'Quality:\s*\+?(\d+)%', l)
            if qm:
                item.quality = int(qm.group(1))

        # Collect mod sections only after item level
        if ilvl_seen:
            mods = [_clean_mod(l) for l in lines if _is_mod_line(l)]
            if mods:
                mod_sections.append(mods)

    # --- Assign implicits / explicits ---
    if mod_sections:
        if len(mod_sections) == 1:
            item.explicits = mod_sections[0]
        else:
            item.implicits = mod_sections[0]
            for sec in mod_sections[1:]:
                item.explicits.extend(sec)

    return item
