"""Build SD import labels against the accepted six-look locales, offline only."""
import json
from native_fl_strings import ROOT, append, sha

OUT = ROOT / '.lab/native-fl-sd-strings'
LABELS = (
    ('import', '从 SD 卡导入', 'Import from SD card'),
    ('confirm', '确认导入配方？', 'Import selected recipe?'),
    ('dirty', '请先保存当前修改', 'Save current changes first'),
    ('invalid', '配方读取失败', 'Cannot read recipe'),
)
HASHES = (
    '741921ec85bd0eea18571479bdd5d0681f78a9d99bacff30305e8721792e40d6',
    '92843d50a15f6d94e95b51eaec0fba7a5a646366f7b954bac05f3c81b923e1f4',
)

def main():
    OUT.mkdir(exist_ok=True)
    records = {}
    resources = None
    for column, language in enumerate(('simplifiedchinese', 'english'), 1):
        name = f'string_{language}.uxc'
        original = (ROOT / '.lab/native-fl-classic-strings' / name).read_bytes()
        if sha(original) != HASHES[column-1]:
            raise ValueError('Accepted locale mismatch: '+name)
        data, ids = append(original, [row[column] for row in LABELS],
                           expected_count=7605, allow_new_blocks=True)
        current = dict(zip((row[0] for row in LABELS), ids))
        if resources is not None and current != resources:
            raise ValueError('Locale resource mismatch')
        resources = current
        (OUT / name).write_bytes(data)
        records[name] = dict(before_sha256=sha(original), after_sha256=sha(data),before_bytes=len(original),after_bytes=len(data))
    proof = dict(kind='sd-additive-locales-v1',resources=resources, files=records,
                 prior_records_preserved_per_locale=7605, flash_ready=False,
                 source_sha256={name: sha((ROOT/name).read_bytes()) for name in (
                     'research/native_fl_sd_strings.py', 'research/native_fl_strings.py',
                     'research/uxc_strings.py')})
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps(resources))

if __name__ == '__main__':
    main()
