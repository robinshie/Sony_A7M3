#!/usr/bin/env python3
"""Run the unchanged sector-transaction tests against the v1-to-v2 correction."""
import argparse
import json
from pathlib import Path
import creative_flash_test as suite

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('kernel','busybox','sony-root'):cli.add_argument('--'+name,required=True,type=Path)
    args=cli.parse_args()
    suite.OUT=suite.ROOT/'.lab/creative-v2'
    suite.test(suite.build(),args.kernel,args.busybox,args.sony_root)
    path=suite.OUT/'qemu-proof.json'
    proof=json.loads(path.read_text())
    proof['source_sha256']['research/creative_fix_test.py']=suite.sha(Path(__file__))
    path.write_text(json.dumps(proof,indent=2)+'\n')
