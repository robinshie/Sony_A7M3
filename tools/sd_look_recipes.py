"""Portable .a7look partial recipes; no camera writes."""
from pathlib import Path
from look_recipes import LOOKS, FIELDS, LOW, HIGH

def list_recipes(root):
    return sorted((p for p in Path(root).iterdir()
                   if not p.is_symlink() and p.is_file()
                   and not p.name.startswith('._')
                   and p.suffix.lower() == '.a7look'), key=lambda p: p.name.casefold())

def parse(data):
    if not 0 < len(data) <= 16384:
        raise ValueError('Recipe must be between 1 and 16384 bytes')
    lines = data.decode('utf-8-sig').splitlines()
    if not lines or lines[0] != 'A7FL-PATCH/1':
        raise ValueError('Unknown recipe format')
    changes = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        key, separator, value = line.partition('=')
        if not separator or key.count('.') != 1:
            raise ValueError('Expected LOOK.field=value')
        look, field = key.split('.')
        if look not in LOOKS or field not in FIELDS or key in changes:
            raise ValueError('Unknown or duplicate setting: '+key)
        digits = value[1:] if value.startswith('-') else value
        if not digits or any(c not in '0123456789' for c in digits):
            raise ValueError('Expected integer: '+key)
        number = int(value)
        index = FIELDS.index(field)
        if not LOW[index] <= number <= HIGH[index]:
            raise ValueError('Setting out of range: '+key)
        changes[key] = number
    if not changes:
        raise ValueError('Empty recipe')
    return changes

def overlay(banks, changes):
    result = [row.copy() for row in banks]
    for key, value in changes.items():
        look, field = key.split('.')
        result[LOOKS.index(look)][FIELDS.index(field)] = value
    return result
