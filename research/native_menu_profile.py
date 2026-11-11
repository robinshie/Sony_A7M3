#!/usr/bin/env python3
"""Derive a minimal native insertion profile from the bounded camera v2 witness.

Reads local artifacts only. These offsets are version-specific and must be
revalidated by the module before any in-memory insertion.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from elf32 import ELF
R=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--usr',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 data=json.loads(subprocess.check_output([sys.executable,str(R/'research/native_menu_probe.py'),'--report',str(a.report)]))
 assert data['status']==3 and not data['overflow'] and len(data['ancestors'])==2
 vb=int(data['view_base'],16);cb=int(data['caution_base'],16)
 assert int(data['manager'][0],16)==vb+0x87f720
 pages={p['relative']:p for cat in data['ancestors'] for p in cat['pages']}
 parents={p['relative']:p for p in data['parents']}
 e=ELF(a.usr/'lib/viewUnified2.so');c=ELF(a.usr/'lib/CautionConfig.so')
 page=pages['0xa6dfa4'];w=[int(s,16) for s in page['node']]
 assert w[0]==cb+0x918ec8 and w[1]==vb+0x8f3214 and w[2]==3 and w[4]==vb+0xa69c88 and w[5]==3 and w[7:9]==[14,14]
 names=[e.relocations[0x8f3214+4*i][1]['name'] for i in range(3)]
 assert names==['cmnViewSettingNodeRootAntiFlickerShoot','cmnViewSettingNodeRootCustomFaceRecognition','cmnViewSettingNodeRootPriorityOnRegisteredFace']
 stock=[{'symbol':s,'caution_offset':c.symbols[s]['value']} for s in names]
 m=parents['0xa6c248'];w=[int(s,16) for s in m['node']]
 assert w[0]==cb+0x918ec8 and w[1]==vb+0xa6b5e0 and w[2]==4 and w[4]==vb+0xa6c400 and w[5]==3 and w[7:9]==[2,2]
 assert [int(x['process'],16) for x in m['children']]==[0x13f,0x29,0x28,0x1ff]
 result={'schema':1,'source_report_sha256':hashlib.sha256(a.report.read_bytes()).hexdigest(),
  'view_sha256':hashlib.sha256(e.data).hexdigest(),'caution_sha256':hashlib.sha256(c.data).hexdigest(),
  'manager_offset':0xa61c18,'manager_vtable_offset':0x87f720,'base_node_vtable_caution_offset':0x918ec8,
  'parents':[{'view_offset':0xa6dfa4,'count':3,'depth':3,'category_offset':0xa69c88,'page':14,'insert_after':2,'children_view_offset':0x8f3214,'stock_children':stock},
             {'view_offset':0xa6c248,'count':4,'depth':3,'category_offset':0xa6c400,'page':2,'insert_after':2,'children_view_offset':0xa6b5e0,'stock_process_ids':[0x13f,0x29,0x28,0x1ff]}],
  'menu_installer_call_va':0x5b9b2c,'menu_installer_lr_va':0x5b9b2f,'original_menu_factory_caller_lr_va':0x20d06d,
  'save_process_id':0x7009,'save_title_resource':0x0204eaab,
  'cold_profiles':[
   {'view_offset':0xa6dfa4,'constructor_call_va':0x22e62e,'children_offset':0x8f3214,'count':3,'properties_offset':0xa725a0,'trailing_fields':[0]*6,'may_stage_without_deep_init':True},
   {'view_offset':0xa6c248,'constructor_call_va':0x22ede2,'children_offset':0xa64e80,'count':0,'properties_offset':0xa72538,'trailing_fields':[0]*6,'may_stage_without_deep_init':False,'reason':'Original runtime repacks this zero-child movie page; defer until initialized live profile matches.'}],
  'required_reinitialization':'For warm attachment, call parent virtual+0xf8 with (parent,NULL,0,parent.depth), then restore FL cursors. Cold still-only staging must skip manual init; original SettingMenu initialization later calls selected root virtual+8 at0x21d0a0. GlobalMenu constructor does not initialize this graph.',
  'scope':'Live original object layout plus original dynamic relocation identities. No camera writes; no physical UI verification.'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n');print(a.out)
if __name__=='__main__':main()
