#!/usr/bin/env python3
"""Build the private curve labels from pinned r12 locales; no camera I/O."""
import json
from pathlib import Path

from native_fl3_strings import OUT as BASE
from native_fl_strings import append, sha

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.lab/native-fl-curve-strings'
LABELS = (
    ('黑位', 'Black Point'), ('暗部', 'Dark Tones'),
    ('中间调', 'Midtones'), ('亮部', 'Light Tones'), ('白位', 'White Point'),
)
KEYS = ('black_point', 'dark_tones', 'midtones', 'light_tones', 'white_point')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    proof = json.loads((BASE / 'proof.json').read_text())
    expected = list(range(0x0204fdaa, 0x0204fdaf))
    names = ('string_simplifiedchinese.uxc', 'string_english.uxc')
    outputs = {}
    for language, name in enumerate(names):
        raw = (BASE / name).read_bytes()
        if sha(raw) != proof['files'][name]['after_sha256']:
            raise ValueError(f'Invalid r12 locale: {name}')
        data, ids = append(raw, [labels[language] for labels in LABELS], expected_count=7594,
                           allow_new_blocks=True)
        if ids != expected:
            raise ValueError('Curve label IDs changed')
        outputs[name] = (raw, data)
    files = {}
    for name, (raw, data) in outputs.items():
        (OUT / name).write_bytes(data)
        files[name] = dict(before_sha256=sha(raw), after_sha256=sha(data), before_bytes=len(raw), after_bytes=len(data))
    sources = ('research/native_fl_curve_strings.py', 'research/native_fl3_strings.py',
               'research/native_fl_strings.py', 'research/uxc_strings.py')
    (OUT / 'proof.json').write_text(json.dumps(dict(
        kind='fl3-curves-additive-locales-v1', resources=dict(zip(KEYS, expected)), files=files,
        source_sha256={name: sha((ROOT / name).read_bytes()) for name in sources},
        flash_ready=False), indent=2) + '\n')
    print('FL3_CURVE_STRINGS_VERIFIED')


if __name__ == '__main__':
    main()
