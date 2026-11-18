"""Build SD import labels against the accepted six-look locales, offline only."""
import json
from native_fl_strings import ROOT, append, sha

OUT = ROOT / '.lab/native-fl-wet-strings'
LABELS = (('wet','湿版黑白（拍后）','Wet plate B&W (after capture)'),('off','关','Off'),('on','开','On'))
HASHES = ('abd89f064761b234623e603a461588f7433dbf1a282e669d413866ac26a7d33b','36bed3b1be93c6fc1ecea704ea487d4baec315543a599e7d01846e87b59feb42')

def main():
    OUT.mkdir(exist_ok=True)
    records = {}
    resources = None
    for column, language in enumerate(('simplifiedchinese', 'english'), 1):
        name = f'string_{language}.uxc'
        original = (ROOT / '.lab/native-fl-custom-strings' / name).read_bytes()
        if sha(original) != HASHES[column-1]:
            raise ValueError('Accepted locale mismatch: '+name)
        data, ids = append(original, [row[column] for row in LABELS],
                           expected_count=7625, allow_new_blocks=True)
        current = dict(zip((row[0] for row in LABELS), ids))
        if resources is not None and current != resources:
            raise ValueError('Locale resource mismatch')
        resources = current
        (OUT / name).write_bytes(data)
        records[name] = dict(before_sha256=sha(original), after_sha256=sha(data),before_bytes=len(original),after_bytes=len(data))
    proof = dict(kind='wet-additive-locales-v1',resources=resources, files=records,
                 prior_records_preserved_per_locale=7625, flash_ready=False,
                 source_sha256={name: sha((ROOT/name).read_bytes()) for name in (
                     'research/native_fl_wet_strings.py', 'research/native_fl_strings.py',
                     'research/uxc_strings.py')})
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps(resources))

if __name__ == '__main__':
    main()
