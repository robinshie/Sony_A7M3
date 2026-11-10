#!/usr/bin/env python3
"""Independently check an image with e2fsck and export each changed file with debugfs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('directory',type=Path)
    args=cli.parse_args();out=args.directory.resolve()
    manifest=json.loads((out/'manifest.json').read_text())
    image=out/'a7m3-retro-wardrobe.img'
    if hashlib.sha256(image.read_bytes()).hexdigest()!=manifest['image_sha256']:raise ValueError('Image hash mismatch')
    subprocess.run(['/opt/homebrew/opt/e2fsprogs/sbin/e2fsck','-fn',str(image)],check=True)
    proof={}
    with tempfile.TemporaryDirectory(dir=out) as temp:
        for index,(name,record) in enumerate(manifest['files'].items()):
            target=Path(temp)/f'{index}.bin'
            subprocess.run(['/opt/homebrew/opt/e2fsprogs/sbin/debugfs','-R',f'dump {name} {target}',str(image)],
                           check=True,capture_output=True)
            digest=hashlib.sha256(target.read_bytes()).hexdigest()
            if digest!=record['after_sha256']:raise ValueError('Independent file mismatch: '+name)
            proof[name]=digest;print('DEBUGFS_FILE_MATCH',name,digest)
    (out/'debugfs-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
