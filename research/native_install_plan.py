#!/usr/bin/env python3
"""Rehearse FL filesystem installation OFFLINE; never a camera flash package.

Uses e2fsprogs for allocation and namespace updates, preserves old locales,
checks each filesystem endstate, and applies the small loader patch last.
"""
import argparse
import hashlib
import json
import math
import mmap
from pathlib import Path
import shutil
import struct
import subprocess
from ext2_patch import Ext2

ROOT=Path(__file__).resolve().parents[1]
DEBUGFS=Path('/opt/homebrew/opt/e2fsprogs/sbin/debugfs')
FSCK=Path('/opt/homebrew/opt/e2fsprogs/sbin/e2fsck')


def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def quoted(path):
    value=str(path)
    if any(c in value for c in ('"','\n','\r','\\')):raise ValueError('Unsupported debugfs path')
    return '"'+value+'"'
def run(args):
    r=subprocess.run([str(x) for x in args],capture_output=True,text=True,check=True)
    return r.stdout+r.stderr
def required_blocks(size,bs):
    data=math.ceil(size/bs);left=max(0,data-12);p=bs//4;meta=0
    if left:meta+=1;left=max(0,left-p)
    if left:meta+=1+math.ceil(min(left,p*p)/p);left=max(0,left-p*p)
    if left:meta+=1+math.ceil(left/(p*p))+math.ceil(left/p)
    return data+meta


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--base',type=Path,default=ROOT/'.lab/creative-icons-belt')
    cli.add_argument('--strings',type=Path,default=ROOT/'.lab/native-fl-strings')
    cli.add_argument('--loader',type=Path,default=ROOT/'.lab/native-menu-loader')
    cli.add_argument('--module',type=Path)
    cli.add_argument('--out',type=Path,default=ROOT/'.lab/native-install-plan')
    a=cli.parse_args();out=a.out;out.mkdir(parents=True,exist_ok=True)
    (out/'manifest.json').unlink(missing_ok=True)
    prior=json.loads((a.base/'manifest.json').read_text())
    base=a.base/'a7m3-retro-wardrobe.img'
    if file_sha(base)!=prior['image_sha256']:raise ValueError('Wrong baseline image')
    strings=json.loads((a.strings/'proof.json').read_text())
    loader=json.loads((a.loader/'proof.json').read_text())
    for proof in (strings,loader):
        for path,digest in proof['source_sha256'].items():
            if file_sha(ROOT/path)!=digest:raise ValueError('Stale source proof: '+path)
    placeholder=a.module is None
    module=out/'a7fl.so'
    if placeholder:
        (out/'placeholder.c').write_text('int a7_fl_install(unsigned base, void *manager) {(void)base;(void)manager;return 0;}\n')
        run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-fPIC','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Os','-c',out/'placeholder.c','-o',out/'placeholder.o'])
        run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',out/'placeholder.o','-o',module])
    else:shutil.copyfile(a.module,module)
    raw=module.read_bytes()
    if raw[:7]!=b'\x7fELF\x01\x01\x01' or raw[16:20]!=b'\x03\0(\0':raise ValueError('Module must be ARM ELF32 ET_DYN')
    with base.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as image:
        fs=Ext2(image);bs=fs.bs;free_blocks=fs.u32(1036);free_inodes=fs.u32(1040)
        old_view=fs.contents(fs.find('/lib/viewUnified2.so'))
        if sha(old_view)!=loader['before_sha256']:raise ValueError('Wrong deployed loader file preimage')
        try:fs.find('/lib/a7fl.so')
        except ValueError as error:
            if not str(error).startswith('File not found:'):raise
        else:raise ValueError('Module path already exists')
        namespace=[]
        for lang,tag in [('simplifiedchinese','zh'),('english','en')]:
            name=f'string_{lang}.uxc';path='/share/app/'+name
            old=fs.contents(fs.find(path));new=(a.strings/name).read_bytes()
            if sha(old)!=strings['files'][name]['before_sha256'] or sha(new)!=strings['files'][name]['after_sha256']:raise ValueError('Locale preimage/output mismatch')
            candidate=f'/share/app/.a7fl-{tag}.new';backup=f'/share/app/.a7fl-{tag}.orig'
            for absent in (candidate,backup):
                try:fs.find(absent)
                except ValueError as error:
                    if not str(error).startswith('File not found:'):raise
                else:raise ValueError('Staging or backup path already exists')
            (out/(name+'.before')).write_bytes(old);(out/name).write_bytes(new)
            namespace.append({'path':path,'candidate':candidate,'backup':backup,'local':name,
                              'before_sha256':sha(old),'after_sha256':sha(new),'before_bytes':len(old),'after_bytes':len(new)})
        dimensions={'partition_bytes':len(image),'filesystem_bytes':fs.blocks*bs,'block_size':bs,
                    'free_blocks':free_blocks,'free_bytes':free_blocks*bs,'free_inodes':free_inodes,
                    'journal':bool(fs.u32(1116)&4),'filesystem_state':fs.u16(1082)}
    new_view=(a.loader/'viewUnified2.so').read_bytes()
    if sha(new_view)!=loader['after_sha256'] or len(new_view)!=len(old_view):raise ValueError('Loader output changed')
    loader_patches=[];allowed=set()
    for name,patch in loader['patches'].items():
        at=patch['va'];n=patch['size'];old=bytes.fromhex(patch['before_hex']);new=bytes.fromhex(patch['after_hex'])
        if old_view[at:at+n]!=old or new_view[at:at+n]!=new:raise ValueError('Loader patch record mismatch')
        allowed.update(range(at,at+n));loader_patches.append({'name':name,'file_offset':at,'bytes':n,'before_hex':old.hex(),'after_hex':new.hex()})
    if any(i not in allowed for i,(x,y) in enumerate(zip(old_view,new_view)) if x!=y):raise ValueError('Loader changed unrelated bytes')
    loader_patches.sort(key=lambda p:(p['name']=='menu_hook',p['file_offset']))
    needed=required_blocks(len(raw),bs)+sum(required_blocks(r['after_bytes'],bs) for r in namespace)+8
    full_cow=needed+required_blocks(len(new_view),bs)
    if free_blocks<needed or free_inodes<3:raise ValueError('Insufficient module/locale COW space')
    image=out/'rehearsal.img';shutil.copyfile(base,image)
    def commands(name,lines):
        script=out/(name+'.debugfs');script.write_text('\n'.join(lines)+'\n')
        log=run([DEBUGFS,'-w','-f',script,image]);(out/(name+'.log')).write_text(log)
        if any(x in log.lower() for x in ('file not found','no free','usage:','already exists','invalid argument')):raise ValueError('debugfs reported staging error')
    def check_fs(name):
        log=run([FSCK,'-fn',image]);(out/(name+'-e2fsck.log')).write_text(log)
        return {'image_sha256':file_sha(image),'e2fsck_log_sha256':sha(log.encode())}
    def verify_file(path,expected,tag):
        target=out/('export-'+tag);target.unlink(missing_ok=True)
        run([DEBUGFS,'-R','dump '+quoted(path)+' '+quoted(target),image])
        if not target.exists() or file_sha(target)!=expected:raise ValueError('Independent debugfs file verification failed: '+path)
        target.unlink()
    stage_lines=['write '+quoted(module)+' /lib/a7fl.so','sif /lib/a7fl.so mode 0100555','sif /lib/a7fl.so uid 0','sif /lib/a7fl.so gid 0']
    for record in namespace:
        stage_lines+=['write '+quoted(out/record['local'])+' '+record['candidate'],
                      'sif '+record['candidate']+' mode 0100444']
    commands('stage',stage_lines)
    staged=check_fs('stage')
    verify_file('/lib/a7fl.so',sha(raw),'module')
    for r in namespace:
        verify_file(r['path'],r['before_sha256'],r['local']+'-old')
        verify_file(r['candidate'],r['after_sha256'],r['local']+'-candidate')
    # Offline rename-equivalent endpoint. Live installer must use kernel
    # link()+rename()+fsync(), never these debugfs operations or raw metadata.
    publish=[]
    for r in namespace:
        publish+=['ln '+r['path']+' '+r['backup'],'sif '+r['path']+' links_count 2',
                  'rm '+r['path'],'ln '+r['candidate']+' '+r['path'],
                  'sif '+r['candidate']+' links_count 2','rm '+r['candidate']]
    commands('publish',publish)
    published=check_fs('publish')
    for r in namespace:
        verify_file(r['path'],r['after_sha256'],r['local']+'-new')
        verify_file(r['backup'],r['before_sha256'],r['local']+'-backup')
    with image.open('r+b') as stream,mmap.mmap(stream.fileno(),0) as edited:
        fs=Ext2(edited);fs.replace('/lib/viewUnified2.so',old_view,new_view);edited.flush()
    activated=check_fs('activate')
    verify_file('/lib/viewUnified2.so',sha(new_view),'view')
    manifest={'package_kind':'offline-filesystem-install-rehearsal-v1','flash_ready':False,'live_writer_implemented':False,
              'module_placeholder':placeholder,'module_integration_verified':False,
              'model':'ILCE-7M3','firmware':'4.04','mount':'/usr','device':'/dev/nflasha15',
              'baseline_image_sha256':prior['image_sha256'],'dimensions':dimensions,
              'capacity':{'module_locales_blocks_with_margin':needed,'full_view_cow_blocks_with_margin':full_cow,
                          'full_view_cow_fits':full_cow<=free_blocks,'full_view_cow_shortfall_bytes':max(0,full_cow-free_blocks)*bs},
              'module':{'path':'/usr/lib/a7fl.so','sha256':sha(raw),'bytes':len(raw)},'locales':namespace,
              'loader_file':'/usr/lib/viewUnified2.so','loader_patches_activation_last':loader_patches,
              'offline_stage':staged,'offline_publish':published,'offline_activate':activated,
              'source_sha256':{'research/native_install_plan.py':file_sha(Path(__file__))},
              'proof_sha256':{'strings':file_sha(a.strings/'proof.json'),'loader':file_sha(a.loader/'proof.json')},
              'required_live_gates':['root/CAP_SYS_ADMIN','exact ro ext2 mount and writable block device',
                 'successful kernel remount rw, independently observed','space/inodes rechecked live',
                 'all file preimages and module integration verified','durable transaction journal and backups',
                 'pending loader hot-patch/cache safety resolution','successful remount ro and cold reboot',
                 'postboot readback and UI/runtime checks']}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print('NATIVE_INSTALL_OFFLINE_REHEARSAL_PASSED placeholder='+str(placeholder))
    print(json.dumps(manifest['capacity']))


if __name__=='__main__':main()
