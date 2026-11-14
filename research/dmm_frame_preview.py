#!/usr/bin/env python3
"""Visualize explicit YUV layout hypotheses from a verified sparse DMM export.

These images are decoding candidates, not proof of the Sony layout, color matrix
or writable frame ownership. The source bytes are never changed.
"""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

def sha(data):return hashlib.sha256(data).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def rgb(y,u,v,limited):
    y=y.astype(np.float32);u=u.astype(np.float32)-128;v=v.astype(np.float32)-128
    if limited:y=(y-16)*(255/219);u*=255/224;v*=255/224
    return Image.fromarray(np.clip(np.stack((y+1.5748*v,y-.187324*u-.468124*v,y+1.8556*u),axis=2),0,255).astype(np.uint8))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace',type=Path);a=p.parse_args()
    folder=a.trace.resolve();report=json.loads((folder/'live.json').read_text());raw=(folder/'frame.raw').read_bytes()
    require(report.get('frame_exported') and report.get('camera_frame_removed') and sha(raw)==report['frame_sha256'],'Unverified or incomplete export')
    require(report.get('sampling')==dict(row_bytes=1920,row_step=16) and len(raw)==261120,'Unsupported diagnostic sample pattern')
    q=report['unit_query'];m=q['metadata']
    require(q['phase']==4 and not q['held'] and not q['pending'] and not q['constructed'] and
            m['canvas_width']==1920 and m['canvas_height']==1080 and m['valid_x']==0 and m['valid_y']==0 and
            m['valid_width']==1616 and m['valid_height']==1080,'Unexpected geometry/lifetime')
    b=np.frombuffer(raw,dtype=np.uint8);rows=b.reshape(136,1920)
    pairs=rows.reshape(136,480,4)
    packed_y=np.stack((pairs[:,:,0],pairs[:,:,2]),axis=2).reshape(136,960)
    packed_uy=np.stack((pairs[:,:,1],pairs[:,:,3]),axis=2).reshape(136,960)
    repeat=lambda x:np.repeat(x,2,axis=1)
    semi=rows[68:].reshape(68,960,2)
    u_planar=b[130560:195840].reshape(34,1920)[:,:960]
    v_planar=b[195840:].reshape(34,1920)[:,:960]
    # Crop sampled valid rows, then show each at its source geometry. Packed
    # interpretations cover only the left half of each source line.
    candidates=[
        ('NV16',rows[:68,:1616],repeat(semi[:,:,0])[:,:1616],repeat(semi[:,:,1])[:,:1616],1616),
        ('NV61',rows[:68,:1616],repeat(semi[:,:,1])[:,:1616],repeat(semi[:,:,0])[:,:1616],1616),
        ('YUYV_left',packed_y[:135],repeat(pairs[:135,:,1]),repeat(pairs[:135,:,3]),960),
        ('UYVY_left',packed_uy[:135],repeat(pairs[:135,:,0]),repeat(pairs[:135,:,2]),960),
        ('I422',rows[:68:2,:1616],repeat(u_planar)[:,:1616],repeat(v_planar)[:,:1616],1616),
        ('YV16',rows[:68:2,:1616],repeat(v_planar)[:,:1616],repeat(u_planar)[:,:1616],1616),
        # A 4:2:0 producer could reserve a larger 4:2:2-sized allocation. Only
        # use Y rows matching the sampled chroma rows; ignore its spare tail.
        ('NV12',rows[:68:2,:1616],repeat(semi[:34,:,0])[:,:1616],repeat(semi[:34,:,1])[:,:1616],1616),
        ('NV21',rows[:68:2,:1616],repeat(semi[:34,:,1])[:,:1616],repeat(semi[:34,:,0])[:,:1616],1616),
    ]
    out=folder/'decode-candidates';out.mkdir(exist_ok=True);files={}
    for limited in (False,True):
        label='limited' if limited else 'full';sheet=Image.new('RGB',(1920,800),(20,20,20));draw=ImageDraw.Draw(sheet)
        draw.text((12,8),f'DECODING HYPOTHESES ONLY - BT.709 {label} range - 1/16 byte-row sampling',fill='white')
        for i,(name,y,u,v,width) in enumerate(candidates):
            decoded=rgb(y,u,v,limited);path=out/f'{name}-{label}.png';decoded.save(path);files[path.name]=sha(path.read_bytes())
            # The byte-row sample is vertically sparse. Offer a separately
            # named, aspect-correct display without pretending to restore the
            # missing scanlines or the unexported right side of packed frames.
            display=decoded.resize((width//2,540),Image.Resampling.BILINEAR)
            display_path=out/f'{name}-{label}-display.png';display.save(display_path)
            files[display_path.name]=sha(display_path.read_bytes())
            size=(min(456,math.floor(340*width/1080)),min(340,math.floor(456*1080/width)))
            tile=decoded.resize(size,Image.Resampling.BILINEAR);x=(i%4)*480;y0=40+(i//4)*380
            draw.text((x+10,y0),name+' (not validated)',fill='white');sheet.paste(tile,(x+(480-size[0])//2,y0+24))
        sheet_path=out/f'candidates-{label}.png';sheet.save(sheet_path);files[sheet_path.name]=sha(sheet_path.read_bytes());print(sheet_path)
    (out/'proof.json').write_text(json.dumps(dict(source_sha256=sha(Path(__file__).read_bytes()),frame_sha256=sha(raw),
        source_report_sha256=sha((folder/'live.json').read_bytes()),layout_verified=False,color_matrix_verified=False,
        files=files,sampling=report['sampling'],
        display_note='Display PNGs interpolate missing rows at source aspect; packed candidates contain only the left 960 pixels. No effect applied.'),indent=2)+'\n')
if __name__=='__main__':main()
