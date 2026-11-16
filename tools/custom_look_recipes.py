"""New-look recipe format and offline catalog utilities; no camera I/O.

This format creates independent looks, never overlays a built-in FL bank.
The camera imports this format from SD; this Python utility performs no USB writes.
"""
import copy
import hashlib
import json
import re
from look_recipes import FIELDS, LOW, HIGH, LOOKS, unique

FORMAT = 'A7FL-LOOK/1'
CATALOG = 'A7FL-CATALOG/1'
MAX_BYTES = 16384
MAX_CUSTOM = 16  # Runtime limit; filling all 16 slots has not been physically tested.


def parse(raw):
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('Recipe exceeds size limit')
    item = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique)
    if not isinstance(item, dict) or set(item) != {'format', 'id', 'name', 'base', 'parameters'}:
        raise ValueError('Expected a complete new-look recipe')
    if item['format'] != FORMAT:
        raise ValueError('Not a new-look recipe; parameter patches cannot create looks')
    if not isinstance(item['id'], str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,47}', item['id']):
        raise ValueError('Invalid stable recipe ID')
    name = item['name']
    if (not isinstance(name, str) or not name.strip() or name != name.strip()
            or len(name.encode('utf-8')) > 63 or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError('Invalid display name')
    if item['base'] not in LOOKS:
        raise ValueError('Unknown color base')
    params = item['parameters']
    if not isinstance(params, dict) or set(params) != set(FIELDS):
        raise ValueError('New looks require all 16 independent parameters')
    for key, low, high in zip(FIELDS, LOW, HIGH):
        value = params[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError('Out of range: '+key)
    return item


def encode(item):
    raw = (json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode()
    parse(raw)
    return raw


def empty_catalog():
    return {'format': CATALOG, 'generation': 0, 'next_id': 7, 'looks': []}


def validate_catalog(catalog):
    if (not isinstance(catalog, dict) or set(catalog) != {'format','generation','next_id','looks'}
            or catalog['format'] != CATALOG or type(catalog['generation']) is not int
            or not 0 <= catalog['generation'] < 0xffffffff
            or type(catalog['next_id']) is not int or not 7 <= catalog['next_id'] < 0xffffffff
            or not isinstance(catalog['looks'], list) or len(catalog['looks']) > MAX_CUSTOM):
        raise ValueError('Invalid catalog')
    ids, recipe_ids = set(), set()
    for row in catalog['looks']:
        if not isinstance(row, dict) or set(row) != {'slot_id','recipe','sha256'}:
            raise ValueError('Invalid catalog entry')
        slot = row['slot_id']
        if type(slot) is not int or not 7 <= slot < catalog['next_id'] or slot in ids:
            raise ValueError('Invalid or repeated look ID')
        recipe = parse(encode(row['recipe']))
        if recipe['id'] in recipe_ids or hashlib.sha256(encode(recipe)).hexdigest() != row['sha256']:
            raise ValueError('Duplicate recipe or damaged content')
        ids.add(slot); recipe_ids.add(recipe['id'])
    return catalog


def append(catalog, raw):
    validate_catalog(catalog)
    item = parse(raw)
    for row in catalog['looks']:
        if row['recipe']['id'] == item['id']:
            raise ValueError('Recipe ID already exists; no implicit overwrite')
    if len(catalog['looks']) >= MAX_CUSTOM or catalog['generation'] >= 0xfffffffe or catalog['next_id'] >= 0xfffffffe:
        raise ValueError('Catalog is full')
    result = copy.deepcopy(catalog)
    result['looks'].append({'slot_id': result['next_id'], 'recipe': item,
                           'sha256': hashlib.sha256(encode(item)).hexdigest()})
    result['next_id'] += 1
    result['generation'] += 1
    return validate_catalog(result)
