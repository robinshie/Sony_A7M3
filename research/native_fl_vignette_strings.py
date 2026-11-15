#!/usr/bin/env python3
"""Append the signed capture-vignette label to accepted halation locales."""
import json

from native_fl_halation_strings import OUT as BASE
from native_fl_strings import ROOT, append, sha

OUT = ROOT / '.lab/native-fl-vignette-strings'
LABELS = ('暗角（拍后）', 'Vignette (Capture)')
RESOURCE = 0x0204fdb1


def main():
    base_proof = json.loads((BASE / 'proof.json').read_text())
    OUT.mkdir(exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    files = {}
    for name, label in zip(('string_simplifiedchinese.uxc', 'string_english.uxc'), LABELS):
        raw = (BASE / name).read_bytes()
        if sha(raw) != base_proof['files'][name]['after_sha256']:
            raise ValueError('Wrong r15 locale: ' + name)
        data, ids = append(raw, [label], expected_count=7601, allow_new_blocks=True)
        if ids != [RESOURCE]:
            raise ValueError('Wrong capture-vignette resource ID')
        (OUT / name).write_bytes(data)
        files[name] = dict(before_sha256=sha(raw), after_sha256=sha(data),
                           before_bytes=len(raw), after_bytes=len(data))
    sources = ('research/native_fl_vignette_strings.py', 'research/native_fl_strings.py',
               'research/uxc_strings.py')
    proof = dict(kind='vignette-additive-locales-v1', resources={'capture_vignette': RESOURCE},
                 files=files, source_sha256={n: sha((ROOT / n).read_bytes()) for n in sources},
                 prior_records_preserved_per_locale=7601, flash_ready=False)
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    main()
