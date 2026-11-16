"""New-look catalog regression. Host prototype only; not firmware acceptance."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from custom_look_recipes import append,empty_catalog,encode,parse,validate_catalog,FORMAT
from look_recipes import FIELDS

def reject(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Invalid operation accepted')

params=dict(zip(FIELDS,[0,0,0,0,0,0,3,0,1,0,0,0,0,0,0,0]))
item=dict(format=FORMAT,id='portrait-grain',name='人像颗粒',base='FL6',parameters=params)
a=empty_catalog();original=copy.deepcopy(a);b=append(a,encode(item))
assert a==original and b['looks'][0]['slot_id']==7
other=copy.deepcopy(item);other.update(id='portrait-soft',name='柔和人像');other['parameters']['grain']=3
c=append(b,encode(other));assert c['looks'][1]['slot_id']==8 and b['looks'][0]['recipe']['parameters']['grain']==1
assert validate_catalog(json.loads(json.dumps(c)))==c
reject(lambda:append(c,encode(item)))
bad=copy.deepcopy(c);bad['looks'][0]['recipe']['parameters']['grain']=9
reject(lambda:validate_catalog(bad))
reject(lambda:parse(b'A7FL-PATCH/1\nFL6.grain=1\n'))
bad=copy.deepcopy(item);del bad['parameters']['grain'];reject(lambda:encode(bad))
bad=copy.deepcopy(item);bad['parameters']['grain']=True;reject(lambda:encode(bad))
bad=copy.deepcopy(item);bad['parameters']['grain']=10;reject(lambda:encode(bad))
print('CUSTOM_LOOK_CATALOG_PASSED: independent IDs, names, parameter copies, roundtrip, duplicate rejection, integrity, patch isolation')
