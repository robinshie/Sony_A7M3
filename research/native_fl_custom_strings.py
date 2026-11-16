"""Build SD import labels against the accepted six-look locales, offline only."""
import json
from native_fl_strings import ROOT, append, sha

OUT = ROOT / '.lab/native-fl-custom-strings'
LABELS = tuple((f'custom{i}', f'自定义风格 {i}', f'Custom look {i}') for i in range(1,17))
HASHES = (
    '1836c584333a0133107e15cda9d96e669d75c41fa4f13f2d71940e0e72154252',
    '7cb075ebf0ed4c2d9d262f5400c50b6882ca0a8952db86c582d5b8c2bbba313d',
)

def main():
    OUT.mkdir(exist_ok=True)
    records = {}
    resources = None
    for column, language in enumerate(('simplifiedchinese', 'english'), 1):
        name = f'string_{language}.uxc'
        original = (ROOT / '.lab/native-fl-sd-strings' / name).read_bytes()
        if sha(original) != HASHES[column-1]:
            raise ValueError('Accepted locale mismatch: '+name)
        data, ids = append(original, [row[column] for row in LABELS],
                           expected_count=7609, allow_new_blocks=True)
        current = dict(zip((row[0] for row in LABELS), ids))
        if resources is not None and current != resources:
            raise ValueError('Locale resource mismatch')
        resources = current
        (OUT / name).write_bytes(data)
        records[name] = dict(before_sha256=sha(original), after_sha256=sha(data),before_bytes=len(original),after_bytes=len(data))
    proof = dict(kind='custom-additive-locales-v1',resources=resources, files=records,
                 prior_records_preserved_per_locale=7609, flash_ready=False,
                 source_sha256={name: sha((ROOT/name).read_bytes()) for name in (
                     'research/native_fl_custom_strings.py', 'research/native_fl_strings.py',
                     'research/uxc_strings.py')})
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps(resources))

if __name__ == '__main__':
    main()
