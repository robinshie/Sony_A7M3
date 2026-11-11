#!/usr/bin/env python3
"""Bounded offline metadata-probe tests and ARM build; never contacts USB."""
import ctypes as C,hashlib,json,mmap,os,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.lab/native-fsmeta';sys.path.insert(0,str(ROOT/'research'))
from ext2_patch import Ext2
class Raw(C.Structure):_fields_=[('offset',C.c_uint),('size',C.c_uint),('result',C.c_int),('tag',C.c_uint),('bytes',C.c_ubyte*1024)]
class Stat(C.Structure):_fields_=[('lstat_result',C.c_int),('open_result',C.c_int),('fstat_result',C.c_int),('close_result',C.c_int),('lstat64',C.c_ubyte*104),('fstat64',C.c_ubyte*104)]
class Directory(C.Structure):_fields_=[('open_result',C.c_int),('read_result',C.c_int),('close_result',C.c_int),('size',C.c_uint),('bytes',C.c_ubyte*16384)]
class Report(C.Structure):_fields_=[('header',C.c_uint*16),('raw',Raw*32),('stats',Stat*8),('directories',Directory*2),('mounts',C.c_ubyte*4096)]
CALL=C.CFUNCTYPE(C.c_long,C.c_void_p,*([C.c_long]*7));checks=0
def check(ok,label):
 global checks;checks+=1
 if not ok:raise AssertionError(label)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
 subprocess.run(['cc','-std=c11','-shared','-fPIC','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(ROOT/'research/native_fsmeta.c'),'-o',str(OUT/'test.dylib')],check=True)
 lib=C.CDLL(str(OUT/'test.dylib'));lib.nfm_read.argtypes=[C.POINTER(Report),CALL,C.c_void_p];lib.nfm_read.restype=C.c_int
 source=ROOT/'.lab/creative-icons-belt/a7m3-retro-wardrobe.img'
 with source.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as image:
  fs=Ext2(image)
  def entries(path):
   raw=fs.contents(fs.find(path));at=0;out=[]
   while at<len(raw):
    ino,n,size,kind=struct.unpack_from('<IHBB',raw,at);name=raw[at+8:at+8+size]
    if ino:out.append((ino,name,kind))
    at+=n
   return out
  dirs={p:entries(p) for p in ('/share/app','/lib')}
  class Environment:
   def __init__(self,fault=0,capacity=300*1024*1024,overrides=None,short=False):self.fds={};self.nextfd=10;self.calls=0;self.fault=fault;self.capacity=capacity;self.overrides=overrides or {};self.short=short;self.errors=[]
   def wrapped(self,ctx,n,a,b,c,d,e,f):
    try:return self.call(n,a,b,c)
    except Exception as exc:self.errors.append(str(exc));return -5
   def call(self,n,a,b,c):
    self.calls+=1
    check(n in (3,5,6,19,196,197,217),'probe only invokes read syscalls')
    if self.calls==self.fault:return -5
    if n==5:
     p=C.string_at(a).decode();check(not b&3,'all inputs opened O_RDONLY');check(bool(b&0x8000),'NOFOLLOW on all inputs')
     if p.startswith('/usr/') and p not in ('/usr/lib','/usr/share/app','/usr/lib/viewUnified2.so'):
      try:fs.find(p[4:])
      except ValueError:return -2
     check(p in ('/dev/nflasha15','/proc/self/mounts') or p.startswith('/usr/'),'only intended inputs')
     fd=self.nextfd;self.nextfd+=1;self.fds[fd]=[p,0];return fd
    if n==6:self.fds.pop(a);return 0
    if n==19:
     p,pos=self.fds[a];check(p=='/dev/nflasha15','seek only block device')
     if c==2:return self.capacity
     check(c==0 and 0<=b<=len(image),'bounded seek');self.fds[a][1]=b;return b
    if n in (196,197):
     p=C.string_at(a).decode() if n==196 else self.fds[a][0]
     raw=bytearray(104)
     if p=='/dev/nflasha15':struct.pack_into('<I',raw,16,0x6000)
     else:
      try:inode=fs.find(p[4:])
      except ValueError:return -2
      struct.pack_into('<I',raw,16,fs.u16(inode));struct.pack_into('<Q',raw,48,fs.u32(inode+4));struct.pack_into('<Q',raw,96,inode)
     C.memmove(b,bytes(raw),104);return 0
    p,pos=self.fds[a]
    if n==217:
     raw=b''
     for ino,name,kind in dirs[p[4:]]:
      length=(19+len(name)+1+7)//8*8
      raw+=struct.pack('<QqHB',ino,0,length,kind)+name+b'\0'+bytes(length-20-len(name))
     part=raw[pos:pos+c];self.fds[a][1]+=len(part);C.memmove(b,part,len(part));return len(part)
    check(n==3,'only read left')
    if p=='/dev/nflasha15':
     part=bytearray(image[pos:pos+min(c,53 if self.short else c)])
     for off,data in self.overrides.items():
      begin=max(pos,off);end=min(pos+len(part),off+len(data))
      if begin<end:part[begin-pos:end-pos]=data[begin-off:end-off]
     part=bytes(part)
    else:
     check(p=='/proc/self/mounts','only mounts stream');raw=b'/dev/nflasha15 /usr ext2 ro,relatime,errors=continue 0 0\n';part=raw[pos:pos+c]
    self.fds[a][1]+=len(part);C.memmove(b,part,len(part));return len(part)
  def run(**kw):
   env=Environment(**kw);callback=CALL(env.wrapped);r=Report();rc=lib.nfm_read(C.byref(r),callback,None)
   check(not env.errors,'syscall bridge: '+repr(env.errors));return rc,r,env
  check(C.sizeof(Report)==72032,'fixed report ABI')
  rc,r,env=run();check(rc==0 and r.header[6]==1 and r.header[7]==22,'baseline geometry and two dynamic locale inodes')
  check(r.header[9:11]==[8,2] and r.directories[0].size>0,'VFS metadata and full directories')
  for block in r.raw[:r.header[7]]:check(block.result==0 and bytes(block.bytes)==image[block.offset:block.offset+1024],'exact raw block bytes')
  check(not env.fds,'all successful input descriptors closed');calls=env.calls
  check(run(short=True)[0]==0,'short reads assembled')
  check(run(capacity=300*1024*1024-512)[0]!=0,'wrong partition capacity rejected')
  check(run(overrides={1080:b'\0\0'})[0]!=0,'foreign superblock rejected')
  check(run(overrides={73928704+4:b'\4\0'})[0]!=0,'short ext2 directory record rejected')
  check(run(overrides={2048+8*32+8:struct.pack('<I',212172)})[0]!=0,'out-of-device inode table rejected')
  # Independent views: raw directory refers to a different in-bounds inode,
  # while VFS retains its original lookup. Do not claim the two must match.
  rc,different,_=run(overrides={17866780:struct.pack('<I',53100)})
  check(rc==0 and any(x.tag==0x10000000|53100 for x in different.raw),'raw/VFS divergence captured without mutation')
  check(bytes(different.stats[2].fstat64)==bytes(r.stats[2].fstat64),'VFS observation independent from raw metadata')
  for fault in (1,2,3,4,5,10,20,30,50,calls):
   rc,failed,_=run(fault=fault);check(rc!=0 or failed.header[4]!=0,'injected fault reported')
  (OUT/'baseline-report.bin').write_bytes(bytes(r))
 flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-fPIC','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
 for name in ('native_fsmeta','native_fsmeta_entry'):
  subprocess.run(['arm-none-eabi-gcc',*flags,'-c',str(ROOT/'research'/(name+'.c')),'-o',str(OUT/(name+'.o'))],check=True)
 subprocess.run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',str(OUT/'native_fsmeta.o'),str(OUT/'native_fsmeta_entry.o'),'-o',str(OUT/'inspect.so')],check=True)
 proof={'source_sha256':{n:digest(ROOT/n) for n in ('research/native_fsmeta.h','research/native_fsmeta.c','research/native_fsmeta_entry.c','research/native_fsmeta_test.py')},'payload_sha256':digest(OUT/'inspect.so'),'report_size':72032,'report_path':'/tmp/jiritsu/a7fsmeta.bin','checks':checks,'scope':'Host syscall-shim tests using private ext2 image, read-only syscall allowlist, short reads, geometry guards, malformed metadata, raw/VFS divergence, selected I/O faults; no-undefined ARM cross-link. No live USB execution.'}
 (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('NATIVE_FSMETA_PASSED',checks,digest(OUT/'inspect.so'))
if __name__=='__main__':main()
