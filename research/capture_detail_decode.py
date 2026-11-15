#!/usr/bin/env python3
"""Decode verified in-call JPEG metadata, not pixels or a writable frame lease."""
import argparse,json,struct
from pathlib import Path
from capture_grain_route import Flat
from yc_route_audit import call,instruction,require,sha,AVCAM_SHA
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bundle',type=Path,required=True);p.add_argument('--avcam',type=Path,required=True)
a=p.parse_args();proof=json.loads((a.bundle/'proof.json').read_text())
require(proof.get('route')=='detail','Not a detail trace')
runs=[r for r in proof['live'] if r['action']=='collect' and r['verified']]
require(bool(runs),'No verified capture collection');r=runs[-1];v=r['values']
require(v[5]==1,'Original calls were not restored')
e=Flat(a.avcam.read_bytes());require(sha(e.data)==AVCAM_SHA,'Wrong original AV-CAM')
result=dict(trace_sha256=sha((a.bundle/r['report_file']).read_bytes()),avcam_sha256=AVCAM_SHA,
    calls=[call(e,s,t,'bl') for s,t in [(0x11b344,0x11ac9c),(0x11adf0,0x1180b8),
      (0x12f1c8,0x6c1984),(0x12f228,0x6c1984),(0x12f256,0x6c1afc),(0x46499c,0x45e504)]],
    pins=[instruction(e,s,op,args) for s,op,args in [
      (0x11acda,'strb.w','r3, [sp, #0x14]'),(0x11ad1a,'movs','r2, #3'),
      (0x11ad1c,'str','r2, [sp, #0x70]'),(0x45e50c,'cmp','r0, #3'),
      (0x45e512,'beq.w','#0x45e622')]],
    samples=[],pixel_write=False,firmware_written=False,writable_lease_proven=False)
for label,at in [('first',16),('latest',192)]:
    s=v[at:at+176];require(s[0]==3 and s[1]==s[175] and not any(s[166:171]),'Incomplete snapshot')
    b=struct.pack('<60I',*s[10:70])
    def words(at,n):return list(struct.unpack_from('<'+str(n)+'I',b,at))
    def descriptor(at):
        count=b[at];require(count<=8,'Invalid range count')
        return dict(count=count,ranges=[dict(address=hex(x),size=y) for x,y in
            (struct.unpack_from('<II',b,at+4+8*i) for i in range(count))])
    sample=dict(label=label,sequence=s[1],source=descriptor(4),destination=descriptor(0x70),
        geometry=dict(format=hex(words(0x48,1)[0]),fields_u16=list(struct.unpack_from('<10H',b,0x4c))),
        source_mode=words(0x60,1)[0],source_format=words(0x64,1)[0],
        destination_region=words(0xb4,4),picture_size_u16=list(struct.unpack_from('<HH',b,0xc4)))
    result['samples'].append(sample)
result['finding']='Both snapshots use source mode 3 and zero source ranges; the current call exposes no CPU-addressable input span. The original checker bypasses range validation for mode 3. This does not prove an alternate memory route or pixel ownership.'
result['source_sha256']={str(Path(__file__).relative_to(Path(__file__).resolve().parents[1])):sha(Path(__file__).read_bytes())}
(a.bundle/'decoded.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('samples','finding')},indent=2))
