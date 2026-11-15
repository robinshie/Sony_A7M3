#!/usr/bin/env python3
"""Append the signed capture-halation label to the verified r15 locales."""
import json

from native_fl_grain_strings import OUT as BASE
from native_fl_strings import ROOT, append, sha

OUT = ROOT / '.lab/native-fl-halation-strings'
LABELS = ('光晕（拍后）', 'Halation (Capture)')
RESOURCE = 0x0204fdb0


def main():
    base_proof = json.loads((BASE / 'proof.json').read_text())
    OUT.mkdir(exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    files = {}
    for name, label in zip(('string_simplifiedchinese.uxc', 'string_english.uxc'), LABELS):
        raw = (BASE / name).read_bytes()
        if sha(raw) != base_proof['files'][name]['after_sha256']:
            raise ValueError('Wrong r15 locale: ' + name)
        data, ids = append(raw, [label], expected_count=7600, allow_new_blocks=True)
        if ids != [RESOURCE]:
            raise ValueError('Wrong capture-halation resource ID')
        (OUT / name).write_bytes(data)
        files[name] = dict(before_sha256=sha(raw), after_sha256=sha(data),
                           before_bytes=len(raw), after_bytes=len(data))
    sources = ('research/native_fl_halation_strings.py', 'research/native_fl_strings.py',
               'research/uxc_strings.py')
    proof = dict(kind='halation-additive-locales-v1', resources={'capture_halation': RESOURCE},
                 files=files, source_sha256={n: sha((ROOT / n).read_bytes()) for n in sources},
                 prior_records_preserved_per_locale=7600, flash_ready=False)
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    main()
