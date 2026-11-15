#!/usr/bin/env python3
"""Append FL4–FL6 labels to the exact accepted vignette locales."""
import json

from native_fl_strings import ROOT, append, sha
from native_fl_vignette_strings import OUT as BASE

OUT = ROOT / '.lab/native-fl-classic-strings'
LABELS = (
    ('fl4', 'FL4（经典负片）', 'FL4 (Classic Negative)'),
    ('fl5', 'FL5（经典纪实）', 'FL5 (Classic Documentary)'),
    ('fl6', 'FL6（自然人像）', 'FL6 (Natural Portrait)'),
)
BASE_HASHES = (
    '99c3292522faeb0bcd6e8ede63cc2da41baf54ff572901273007fbc2eef9d611',
    '4e797657592371db1eb1912e73e9c928ac7dbbe93df0d711b26ce5c86f6f47d0',
)


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    files = {}
    resources = {key: 0x0204fdb2+i for i, (key, _, _) in enumerate(LABELS)}
    for column, language in enumerate(('simplifiedchinese', 'english'), 1):
        name = f'string_{language}.uxc'
        raw = (BASE / name).read_bytes()
        if sha(raw) != BASE_HASHES[column-1]:
            raise ValueError('Wrong r16 locale: '+name)
        data, ids = append(raw, [row[column] for row in LABELS], expected_count=7602,
                           allow_new_blocks=True)
        if ids != list(resources.values()):
            raise ValueError('Unexpected classic look resources')
        (OUT / name).write_bytes(data)
        files[name] = dict(before_sha256=sha(raw), after_sha256=sha(data),
                           before_bytes=len(raw), after_bytes=len(data))
    sources = ('research/native_fl_classic_strings.py', 'research/native_fl_strings.py',
               'research/uxc_strings.py')
    proof = dict(kind='classic-additive-locales-v1', resources=resources, files=files,
                 source_sha256={n: sha((ROOT / n).read_bytes()) for n in sources},
                 prior_records_preserved_per_locale=7602, flash_ready=False)
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2)+'\n')


if __name__ == '__main__':
    main()
