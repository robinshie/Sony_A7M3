#!/usr/bin/env python3
"""Test atomic single-module upgrade core with real private host files, no camera.

ARM Linux credential/mount/statfs/stat64 syscalls are modeled; file I/O, hardlinks,
symlinks, rename and fsync use a disposable host directory. No payload is bound.
"""
import argparse
import ctypes as C
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from camera.native_module_replace import REVISIONS

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--revision',type=int,choices=sorted(REVISIONS),default=1);REV=parser.parse_args().revision
OUT=ROOT/('.lab/native-module-replace-test'+('' if REV==1 else f'-r{REV}'))
TEMP=REVISIONS[REV]['temporary'];BACKUP=REVISIONS[REV]['backup'];JOURNAL=REVISIONS[REV]['journal']
checks=0
def check(ok,why):
 global checks
 checks+=1
 if not ok:raise AssertionError(why)
class Bundle(C.Structure):
 _fields_=[('version',C.c_uint32),('old_size',C.c_uint32),('new_size',C.c_uint32),('view_size',C.c_uint32),
           ('new_bytes',C.c_void_p),*[(n,C.c_ubyte*32) for n in ('old_sha','new_sha','view_sha','new_proof_sha')]]
class Report(C.Structure):
 _fields_=[(n,C.c_uint32) for n in ('magic','version','phase','created','backed_up','published')]+[(n,C.c_int32) for n in ('status','first_error','rollback_ok','readonly_confirmed')]+[('binding',C.c_ubyte*32)]
CALL=C.CFUNCTYPE(C.c_long,C.c_void_p,*([C.c_long]*7));IDENTITY=C.CFUNCTYPE(C.c_int,C.c_void_p)
OLD=bytes((i*7+3)%251 for i in range(2048))
NEW=bytearray((i*11+5)%251 for i in range(4096));NEW[:7]=b'\x7fELF\x01\x01\x01';NEW[16:20]=b'\x03\0(\0';NEW=bytes(NEW)
VIEW=bytes((i*17+13)%251 for i in range(4096))

class Env:
 def __init__(self,folder):
  self.root=Path(folder);self.lib=self.root/'usr/lib';self.setting=self.root/'setting';self.lib.mkdir(parents=True);self.setting.mkdir()
  (self.lib/'a7fl.so').write_bytes(OLD);(self.lib/'viewUnified2.so').write_bytes(VIEW)
  for revision in range(1,REV):
   (self.lib/REVISIONS[revision]['backup']).write_bytes(b'previous module')
   (self.setting/REVISIONS[revision]['journal']).write_bytes(b'previous journal')
  self.calls=0;self.fail_at=0;self.fds={};self.ro=True;self.fail_ro=False;self.chunk=0;self.stage_writes=0;self.partial_failure=False;self.error=None
  self.model=1;self.version=b'37114_13.2026020901';self.block_ro=0;self.space=10000;self.owner_overrides={}
  self.callback=CALL(self.invoke);self.identity=IDENTITY(lambda _:self.model)
 def allocate(self,item):
  fd=10
  while fd in self.fds:fd+=1
  self.fds[fd]=item;return fd
 def absolute(self,path):return self.root/path.lstrip('/')
 def flags(self,f):
  return (f&3)|(os.O_CREAT if f&64 else 0)|(os.O_EXCL if f&128 else 0)|(os.O_NOFOLLOW if f&0x8000 else 0)|(os.O_NONBLOCK if f&0x800 else 0)|(os.O_DIRECTORY if f&0x4000 else 0)
 def close(self,fd):
  item=self.fds.pop(fd)
  if item[0]=='file':os.close(item[1])
 def invariant(self):
  # Also checked between writes/links/renames: an interruption never exposes a
  # partial new ELF under the real module filename.
  path=self.lib/'a7fl.so'
  if not path.is_symlink():check(path.read_bytes() in (OLD,NEW),'published module always complete old or new')
  check((self.lib/'viewUnified2.so').read_bytes()==VIEW,'view library never changed')
  for revision in range(1,REV):
   check((self.lib/REVISIONS[revision]['backup']).read_bytes()==b'previous module' and (self.setting/REVISIONS[revision]['journal']).read_bytes()==b'previous journal','prior revision backup and journal preserved')
 def invoke(self,ctx,nr,a,b,c,d,e,f):
  try:
   self.calls+=1
   if self.calls==self.fail_at:
    if nr==6:self.close(a)
    return -errno.EIO
   return self.operation(nr,a,b,c,d,e,f)
  except OSError as error:return -error.errno
  except Exception as error:self.error=error;return -errno.EIO
 def operation(self,nr,a,b,c,d,e,f):
  if nr==49:return 0
  if nr==184:C.memmove(b,struct.pack('<6I',0xffffffff,0xffffffff,0xffffffff,0xffffffff,0xffffffff,0xffffffff),24);return 0
  if nr==54:check(b==0x125e,'only read-only block ioctl');C.memmove(c,struct.pack('<i',self.block_ro),4);return 0
  if nr==99:
   fields=[0]*16;fields[0]=0xef53;fields[1]=1024;fields[4]=self.space;fields[6]=1000;fields[11]=4129 if self.ro else 4128
   C.memmove(b,struct.pack('<16I',*fields),64);return 0
  if nr==21:
   check(C.string_at(a)==b'/dev/nflasha15' and C.string_at(b)==b'/usr' and C.string_at(c)==b'ext2','only intended usr remount')
   if d&1 and self.fail_ro:return -errno.EIO
   self.ro=bool(d&1);return 0
  if nr==5:
   path=C.string_at(a).decode()
   if path=='/proc/self/mounts':
    contents=('/dev/nflasha15 /usr ext2 '+('ro' if self.ro else 'rw')+',relatime,errors=continue 0 0\n').encode();return self.allocate(['bytes',contents,0])
   if path=='/version.txt':return self.allocate(['bytes',self.version,0])
   if path=='/dev/nflasha15':check(b&3==0,'block device never writable');return self.allocate(['block',0,0])
   target=self.absolute(path);return self.allocate(['file',os.open(target,self.flags(b),c),target])
  if nr==322:
   parent=self.fds[a];name=C.string_at(b).decode();path=parent[2]/name
   if self.ro and str(path).startswith(str(self.lib)) and c&3:return -errno.EROFS
   return self.allocate(['file',os.open(name,self.flags(c),d,dir_fd=parent[1]),path])
  if nr==6:self.close(a);return 0
  if nr==197:
   item=self.fds[a];s=os.fstat(item[1]);raw=bytearray(104)
   original=item[2] in (self.lib,self.lib/'viewUnified2.so')
   uid,gid=self.owner_overrides.get(str(item[2].relative_to(self.root)),(57285,1000) if original else (0,0))
   struct.pack_into('<Q',raw,0,s.st_dev);struct.pack_into('<IIII',raw,16,s.st_mode,s.st_nlink,uid,gid)
   struct.pack_into('<Q',raw,48,s.st_size);struct.pack_into('<Q',raw,96,s.st_ino);C.memmove(b,bytes(raw),104);return 0
  if nr==3:
   item=self.fds[a];size=min(c,self.chunk) if self.chunk else c
   if item[0]=='bytes':raw=item[1][item[2]:item[2]+size];item[2]+=len(raw)
   else:raw=os.read(item[1],size)
   C.memmove(b,raw,len(raw));return len(raw)
  if nr==4:
   item=self.fds[a];check(item[0]=='file' and item[2].name not in ('a7fl.so','viewUnified2.so',BACKUP),'only exclusive candidate/journal may be written')
   if item[2].name==TEMP:
    self.stage_writes+=1
    if self.partial_failure and self.stage_writes==2:return -errno.EIO
   size=min(c,self.chunk) if self.chunk else c;n=os.write(item[1],C.string_at(b,size));self.invariant();return n
  if nr==118:os.fsync(self.fds[a][1]);return 0
  if nr in (328,329,330):
   if self.ro:return -errno.EROFS
   source=self.fds[a];name=C.string_at(b).decode()
   if nr==328:os.unlink(name,dir_fd=source[1])
   else:
    target=self.fds[c];newname=C.string_at(d).decode()
    if nr==329:os.rename(name,newname,src_dir_fd=source[1],dst_dir_fd=target[1])
    else:os.link(name,newname,src_dir_fd=source[1],dst_dir_fd=target[1],follow_symlinks=False)
   self.invariant();return 0
  raise AssertionError('unexpected syscall '+str(nr))

def main():
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
 subprocess.run(['cc',f'-DNMR_REVISION={REV}','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-shared','-fPIC',str(ROOT/'research/native_module_replace.c'),'-o',str(OUT/'core.so')],check=True)
 lib=C.CDLL(str(OUT/'core.so'));lib.nmr_run.argtypes=[C.POINTER(Bundle),C.c_void_p,CALL,C.c_void_p,IDENTITY,C.c_void_p,C.c_int,C.POINTER(Report)]
 blob=C.create_string_buffer(NEW);b=Bundle(REV,len(OLD),len(NEW),len(VIEW),C.cast(blob,C.c_void_p),
        *[(C.c_ubyte*32).from_buffer_copy(hashlib.sha256(v).digest()) for v in (OLD,NEW,VIEW,b'attested-test-proof')])
 expected=(C.c_ubyte*32)();lib.nmr_binding(C.byref(b),expected)
 def run(env,write=1):
  r=Report();result=lib.nmr_run(C.byref(b),expected,env.callback,None,env.identity,None,write,C.byref(r))
  if env.error:raise env.error
  check(not env.fds,'all descriptors closed');env.invariant()
  if r.rollback_ok:check((env.lib/'a7fl.so').read_bytes()==OLD,'claimed rollback restores original inode bytes')
  if not result:check(r.readonly_confirmed and env.ro,'success always confirms read-only mount')
  return r
 with tempfile.TemporaryDirectory(dir=OUT) as td:
  env=Env(td);r=run(env,0);check(r.status==0 and not (env.setting/JOURNAL).exists(),'read/preflight creates no transaction');check((env.lib/'a7fl.so').read_bytes()==OLD,'read keeps original module')
 with tempfile.TemporaryDirectory(dir=OUT) as td:
  env=Env(td);r=run(env);total=env.calls;check(r.status==0 and r.phase==100 and (r.created,r.backed_up,r.published)==(0,1,1),'successful atomic replacement')
  check((env.lib/BACKUP).read_bytes()==OLD,'specific original backup retained')
  r=run(env);check(r.status!=0,'completed replacement never resumes or overwrites journal')
 for point in range(1,total+1):
  with tempfile.TemporaryDirectory(dir=OUT) as td:
   env=Env(td);env.fail_at=point;r=run(env)
   check(r.status!=0,'each injected syscall failure prevents completion');check(env.ro,'single syscall fault ends read-only')
 with tempfile.TemporaryDirectory(dir=OUT) as td:
  env=Env(td);env.chunk=7;r=run(env);check(r.status==0,'short I/O completes exactly')
 with tempfile.TemporaryDirectory(dir=OUT) as td:
  env=Env(td);env.chunk=7;env.partial_failure=True;r=run(env)
  check(r.status!=0 and r.rollback_ok and not (env.lib/TEMP).exists(),'partial candidate write rolls back without publishing')
 for name in ('a7fl.so',TEMP,BACKUP,JOURNAL):
  with tempfile.TemporaryDirectory(dir=OUT) as td:
   env=Env(td);path=(env.setting if name==JOURNAL else env.lib)/name
   if path.exists():path.unlink()
   path.symlink_to('viewUnified2.so');r=run(env)
   check(r.status!=0 and env.ro and not env.stage_writes,'symlink path rejected before candidate writes')
 with tempfile.TemporaryDirectory(dir=OUT) as td:
  env=Env(td);os.link(env.lib/'a7fl.so',env.lib/'unexpected-alias');r=run(env)
  check(r.status!=0 and not (env.setting/JOURNAL).exists(),'old module hardlink alias rejected')
 for field,value in (('model',0),('version',b'other-build'),('block_ro',1),('space',0)):
  with tempfile.TemporaryDirectory(dir=OUT) as td:
   env=Env(td);setattr(env,field,value);r=run(env);check(r.status!=0 and not env.stage_writes,'identity/build/block/space guard rejects')
 with tempfile.TemporaryDirectory(dir=OUT) as td:
  env=Env(td);env.fail_ro=True;r=run(env);check(r.status==-4 and not r.readonly_confirmed,'persistent remount-ro failure remains explicit')
 # Actual Sony stat64 reports: original /usr/lib and view owner57285:1000;
 # our installed module is0:0. The previous blanket uid0 guard rejected them.
 for path,owner,phase in [('usr/lib',(0,0),1006),('usr/lib',(57285,0),1006),
                          ('usr/lib/viewUnified2.so',(0,0),1008),
                          ('usr/lib/a7fl.so',(57285,1000),1007),('setting',(57285,1000),1006)]:
  with tempfile.TemporaryDirectory(dir=OUT) as td:
   env=Env(td);env.owner_overrides[path]=owner;r=run(env)
   check(r.status!=0 and r.phase==phase and not env.stage_writes and not (env.setting/JOURNAL).exists(),
         'per-path unexpected owner rejects before any mutation: '+path)
 for name in ('native_module_replace','native_module_replace_linux'):
  subprocess.run(['arm-none-eabi-gcc',f'-DNMR_REVISION={REV}','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fPIC','-c',str(ROOT/'research'/f'{name}.c'),'-o',str(OUT/f'{name}.o')],check=True)
 subprocess.run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',str(OUT/'native_module_replace.o'),str(OUT/'native_module_replace_linux.o'),'-o',str(OUT/'unbound-core.so')],check=True)
 files=['research/native_module_replace.c','research/native_module_replace.h','research/native_module_replace_linux.c','research/native_module_replace_test.py','payloads/sha256.h']
 h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 proof={'revision':REV,'checks':checks,'fault_points':total,'owner_profile':{'/usr/lib':[57285,1000],'/usr/lib/viewUnified2.so':[57285,1000],'/usr/lib/a7fl.so':[0,0],'/setting':[0,0]},'source_sha256':{p:h(ROOT/p) for p in files},'arm_core_sha256':h(OUT/'unbound-core.so'),
        'bound':False,'deployed':False,'scope':'Real private host file I/O/link/rename/fsync, modeled ARM metadata/mount/identity syscalls; no camera or resident-process changes.'}
 (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('NATIVE_MODULE_REPLACE_CHECKS',checks,'FAULT_POINTS',total);print('NATIVE_MODULE_REPLACE_TESTS_PASSED')
if __name__=='__main__':main()
