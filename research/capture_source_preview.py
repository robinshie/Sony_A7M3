#!/usr/bin/env python3
"""Show explicitly labelled pixel-layout hypotheses; no grain/effect is applied."""
import argparse,hashlib,json,struct
from pathlib import Path
from PIL import Image,ImageDraw

def sha(b):return hashlib.sha256(b).hexdigest()
def clamp(v):return max(0,min(255,round(v)))
def color(y,u,v):return (clamp(y+1.5748*(v-128)),clamp(y-.187324*(u-128)-.468124*(v-128)),clamp(y+1.8556*(u-128)))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=Path);a=p.parse_args()
 meta=json.loads((a.bundle/'source-sample.json').read_text());raw=(a.bundle/'source-sample.raw').read_bytes()
 if len(raw)!=97280 or sha(raw)!=meta['sample_sha256'] or not meta['sample_in_call']:raise ValueError('Not a verified source sample')
 rows=[raw[i*1520:(i+1)*1520] for i in range(64)];tiles=[]
 for layout in ('UYVY','YUYV','VYUY','YVYU'):
  pixels=[]
  for r in rows[::2]:
   for at in range(0,1520,4):
    values=dict(zip(layout,(r[at],r[at+1],r[at+2],r[at+3])))
    if layout[0]=='Y':ys=(r[at],r[at+2]);u=r[at+layout.index('U')];v=r[at+layout.index('V')]
    else:ys=(r[at+1],r[at+3]);u=r[at+layout.index('U')];v=r[at+layout.index('V')]
    pixels.extend(color(y,u,v) for y in ys)
  im=Image.new('RGB',(760,32));im.putdata(pixels);tiles.append((layout+' / full-range 709 hypothesis',im))
 words=sorted(struct.unpack('<48640H',raw));lo=words[len(words)//100];hi=words[len(words)*99//100];span=max(1,hi-lo)
 for mode in ('RGGB16','BGGR16','GRBG16','GBRG16'):
  pixels=[]
  for y in range(0,64,2):
   for at in range(0,1520,4):
    aa,bb=struct.unpack_from('<HH',rows[y],at);cc,dd=struct.unpack_from('<HH',rows[y+1],at)
    vals=[clamp((v-lo)*255/span) for v in (aa,bb,cc,dd)]
    pattern=mode[:4];red=vals[pattern.index('R')];blue=vals[pattern.index('B')];green=round(sum(vals[i] for i in range(4) if pattern[i]=='G')/2)
    pixels.append((red,green,blue))
  im=Image.new('RGB',(380,32));im.putdata(pixels);tiles.append((mode+' / percentile normalization',im))
 out=a.bundle/'source-preview';out.mkdir(exist_ok=True)
 sheet=Image.new('RGB',(1600,1140),(24,24,24));d=ImageDraw.Draw(sheet)
 d.text((12,8),'REAL IN-CALL BYTE SAMPLE / LAYOUT HYPOTHESES ONLY / SPARSE ROWS INTERPOLATED / NO FILM EFFECT',fill='white')
 files={}
 for i,(name,im) in enumerate(tiles):
  key=name.split(' ')[0];path=out/(key+'.png');im.save(path);files[path.name]=sha(path.read_bytes())
  display=im.resize((760,500),Image.Resampling.BILINEAR);display.save(out/(key+'-display.png'))
  tile=im.resize((380,250),Image.Resampling.BILINEAR);x=i%4*400;y=40+i//4*550
  d.text((x+6,y),name,fill='white');sheet.paste(tile,(x+10,y+30))
  # Include 1:1 source sample under interpolated display.
  sheet.paste(im.resize((380,32),Image.Resampling.NEAREST),(x+10,y+300))
 path=out/'hypotheses.png';sheet.save(path)
 stats=dict(min_word=words[0],max_word=words[-1],p01=lo,p99=hi,bytes_by_position=[dict(min=min(raw[k::4]),max=max(raw[k::4]),mean=sum(raw[k::4])/len(raw[k::4])) for k in range(4)])
 (out/'proof.json').write_text(json.dumps(dict(sample_sha256=sha(raw),source_sha256=sha(Path(__file__).read_bytes()),files=files,stats=stats,pixel_layout_verified=False,effect_applied=False,frame_lease=False),indent=2)+'\n')
 print(json.dumps(stats,indent=2));print(path)
if __name__=='__main__':main()
