#!/usr/bin/env python3
"""Build a guarded correction on top of the exact deployed v2 creative image."""
import hashlib
import json
import mmap
from pathlib import Path
import shutil
import struct
import sys

from ext2_patch import Ext2
from uxc_strings import Strings

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_image import verify_build
from local import IMAGE,LAB,sha,file_sha

OUT=LAB/'creative-v3'

def build():
    verify_build()
    prior=json.loads((LAB/'creative-v2/manifest.json').read_text())
    base_image=LAB/'creative-v2/a7m3-retro-wardrobe.img'
    if file_sha(base_image)!=prior['image_sha256']:raise ValueError('Wrong deployed v2 image')
    native=LAB/'menu-identity'
    proof=json.loads((native/'proof.json').read_text())
    for path,digest in proof['source_sha256'].items():
        if sha((ROOT/path).read_bytes())!=digest:raise ValueError('Native test is stale: '+path)
    for path,digest in proof['files'].items():
        if sha((native/path).read_bytes())!=digest:raise ValueError('Native binary changed: '+path)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'manifest.json').unlink(missing_ok=True)
    target=OUT/'a7m3-retro-wardrobe.img'
    shutil.copyfile(base_image,target)
    files={}
    with base_image.open('rb') as original,target.open('r+b') as edited:
        before=mmap.mmap(original.fileno(),0,access=mmap.ACCESS_READ)
        after=mmap.mmap(edited.fileno(),0)
        fs=Ext2(after)
        for name in ('viewUnified2.so','string_simplifiedchinese.uxc','string_english.uxc','CautionConfig.so'):
            path='/lib/'+name if name.endswith('.so') else '/share/app/'+name
            inode=fs.find(path);old=fs.contents(inode)
            expected=prior['files'][path]['after_sha256'] if path in prior['files'] else proof['config_sha256']
            if sha(old)!=expected:raise ValueError('Wrong deployed file preimage')
            if name.endswith('.so'):
                new=(native/name).read_bytes()
                # Activate by changing the menu-creation call only after all helper code.
                file_off=proof['init_file_offset']
                if name=='viewUnified2.so':activation=(fs.block(inode,file_off//fs.bs)*fs.bs+file_off%fs.bs)//512*512
            else:new=old  # Preserve both locale resources and earlier title edits.
            fs.replace(path,old,new)
            files[path]={'before_sha256':sha(old),'after_sha256':sha(new),
                         'before_bytes':len(old),'after_bytes':len(new),'inode_offset':inode}
            (OUT/name).write_bytes(new)
        after.flush()
        offsets=[off for off in range(0,len(before),512) if before[off:off+512]!=after[off:off+512]]
        if activation not in offsets or not 1<len(offsets)<=32:raise ValueError('Unexpected sector count')
        offsets.remove(activation);offsets.append(activation)
        header=before[:2048]
        if any(off<2048 for off in offsets):raise ValueError('Filesystem header must not change')
        (OUT/'header.bin').write_bytes(header)
        (OUT/'offsets.bin').write_bytes(struct.pack('<'+'I'*len(offsets),*offsets))
        (OUT/'before.bin').write_bytes(b''.join(before[o:o+512] for o in offsets))
        (OUT/'after.bin').write_bytes(b''.join(after[o:o+512] for o in offsets))
        changed=sum(sum(x!=y for x,y in zip(before[o:o+512],after[o:o+512])) for o in offsets)
        before.close();after.close()
    manifest={'model':'ILCE-7M3','firmware':'4.04','partition':'/dev/nflasha15',
              'preimage_sha256':prior['image_sha256'],'image_sha256':file_sha(target),
              'sectors':offsets,'activation_sector':activation,'changed_bytes':changed,'files':files,
              'native_proof_sha256':sha((native/'proof.json').read_bytes()),'native_directory':'menu-identity',
              'previous_package':'creative-v2',
              'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in ('research/ext2_patch.py','research/build_creative_identity.py')},
              'blobs':{p:sha((OUT/p).read_bytes()) for p in ('header.bin','offsets.bin','before.bin','after.bin')}}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':build()
