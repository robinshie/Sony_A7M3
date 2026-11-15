#!/usr/bin/env python3
"""Append capture-grain labels to exact accepted r14 locales; no USB."""
import json
from native_fl_curve_strings import OUT as BASE
from native_fl_strings import ROOT, append, sha
OUT=ROOT/'.lab/native-fl-grain-strings'
LABELS=('颗粒（拍后）','Grain (Capture)')
def main():
    proof=json.loads((BASE/'proof.json').read_text());OUT.mkdir(exist_ok=True)
    (OUT/'proof.json').unlink(missing_ok=True);files={}
    for i,name in enumerate(('string_simplifiedchinese.uxc','string_english.uxc')):
        raw=(BASE/name).read_bytes()
        if sha(raw)!=proof['files'][name]['after_sha256']:raise ValueError('Wrong r14 locale')
        data,ids=append(raw,[LABELS[i]],expected_count=7599,allow_new_blocks=True)
        if ids!=[0x0204fdaf]:raise ValueError('Wrong grain resource ID')
        (OUT/name).write_bytes(data)
        files[name]=dict(before_sha256=sha(raw),after_sha256=sha(data),before_bytes=len(raw),after_bytes=len(data))
    sources=('research/native_fl_grain_strings.py','research/native_fl_strings.py','research/uxc_strings.py')
    (OUT/'proof.json').write_text(json.dumps(dict(kind='grain-additive-locales-v1',resources={'capture_grain':0x0204fdaf},files=files,
        source_sha256={n:sha((ROOT/n).read_bytes()) for n in sources},prior_records_preserved_per_locale=7599,flash_ready=False),indent=2)+'\n')
    print('CAPTURE_GRAIN_STRINGS_VERIFIED')
if __name__=='__main__':main()
