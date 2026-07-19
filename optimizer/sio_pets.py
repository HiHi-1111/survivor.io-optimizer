"""sIO normal and Xeno pet CE stat assembly."""
from __future__ import annotations
import math
from typing import Any,Mapping
from optimizer.sio_pet_data import SIO_PET_DATA
from optimizer.sio_ce_constants import SIO_DIRECT_DAMAGE_COEFFICIENTS

XENO_NAMES=['Capy','Crucker','Puffo','King Blizzblast','Nutjob','Gourmeow']
NORMAL_SKILLS=['Motivation','Inspiration','Encouragement','Battle Lust','Gary']
XENO_SKILL_MAP={'Sync Rate':'xenoSyncRate','Resonance Chance':'xenoResChance','Resonance Damage':'xenoResDamage','Shield Damage':'shieldDamage','Dmg to Poisoned':'poisoned','Dmg to Weakened':'weakened','Dmg to Chilled':'chilled','Atk Percent':'atkPercent'}
XENO_SKILL_VALUES={'xenoResChance':[0,3,6,6,9,9,15,15,22.5,22.5,30],'xenoResDamage':[0,3,6,6,9,9,15,15,22.5,22.5,30],'shieldDamage':[0,4,8,8,12,12,20,20,30,30,40],'poisoned':[0,5,10,10,15,15,25,25,37.5,37.5,50],'weakened':[0,5,10,10,15,15,25,25,37.5,37.5,50],'chilled':[0,5,10,10,15,15,25,25,37.5,37.5,50],'atkPercent':[0,4,8,8,12,12,20,20,30,30,40]}

def _num(v,d=0.0):
 try:x=float(v)
 except (TypeError,ValueError):return d
 return x if math.isfinite(x) else d

def _add(o,src):
 for k,v in (src or {}).items():
  x=_num(v)
  if x:o[str(k)]=o.get(str(k),0)+x

def _threshold(table,level):
 chosen=None
 for n,v in zip((table or {}).get('nums',[]) or [],(table or {}).get('vals',[]) or []):
  if level<_num(n):break
  chosen=v
 return chosen or {}

def _unwrap(v):return v.get('data') if isinstance(v,Mapping) and isinstance(v.get('data'),Mapping) else v

def pet_state(profile):
 sio=profile.get('sio_ce') if isinstance(profile.get('sio_ce'),Mapping) else {}
 raw=_unwrap(sio.get('pets') or profile.get('pets') or {})
 return dict(raw) if isinstance(raw,Mapping) else {}

def pet_skill_state(profile):
 sio=profile.get('sio_ce') if isinstance(profile.get('sio_ce'),Mapping) else {}
 raw=_unwrap(sio.get('petSkills') or profile.get('petSkills') or {})
 return dict(raw) if isinstance(raw,Mapping) else {}

def _collectible_set_bonus(profile,out):
 sio=profile.get('sio_ce') if isinstance(profile.get('sio_ce'),Mapping) else {}
 raw=_unwrap(sio.get('collectibles') or profile.get('collectibles') or {})
 if isinstance(raw,Mapping) and isinstance(raw.get('owned'),Mapping):raw=raw['owned']
 names=['Memory Editor','Temporal Rewinder','Spatial Rewinder','Holodream Fluid']
 stars=[_num((raw.get(n) or {}).get('stars') if isinstance(raw.get(n),Mapping) else raw.get(n)) for n in names] if isinstance(raw,Mapping) else [0]*4
 if min(stars)>=3:out['xenoSyncRate']=out.get('xenoSyncRate',0)+10
 if sum(stars)>=25:out['xenoResDuration']=out.get('xenoResDuration',0)+1

def assemble_sio_pet_stats(profile:Mapping[str,Any])->dict[str,Any]:
 data=SIO_PET_DATA;pets=pet_state(profile);skills=pet_skill_state(profile)
 active=str(pets.get('active') or pets.get('main_pet') or '');stars=pets.get('stars',{}) if isinstance(pets.get('stars'),Mapping) else pets.get('awakened',{}) if isinstance(pets.get('awakened'),Mapping) else {}
 if not active:return {'stats':{},'detail':{},'warnings':[]}
 star=int(_num(stars.get(active)));definition=data['pets'].get(active)
 if not definition:return {'stats':{},'detail':{},'warnings':[f'Unknown sIO pet: {active}']}
 out={};_add(out,_threshold(definition.get('stars'),star));ptype=definition.get('type')
 detail={'active':active,'stars':star,'type':ptype}
 if ptype=='Default':
  for name in NORMAL_SKILLS:
   state=skills.get(name) or {}
   if isinstance(state,Mapping) and state.get('enabled'):
    rarity=str(state.get('rarity') or 'Excellent');_add(out,(data['petSkills']['Default'].get(name) or {}).get(rarity))
 else:
  out['xenoSyncRate']=_num((skills.get('Sync Rate') or {}).get('value') if isinstance(skills.get('Sync Rate'),Mapping) else skills.get('Sync Rate'))
  out['xenoResChance']=out.get('xenoResChance',0)+10;out['xenoResDamage']=out.get('xenoResDamage',0)+10
  support=pets.get('support',[]) if isinstance(pets.get('support'),list) else []
  for index,row in enumerate(support):
   if not isinstance(row,Mapping):continue
   pet=active if index==0 else str(row.get('name') or '')
   pstar=int(_num(stars.get(pet)))
   for label in row.get('skill',[]) or []:
    key=XENO_SKILL_MAP.get(str(label),str(label));vals=XENO_SKILL_VALUES.get(key)
    if vals:out[key]=out.get(key,0)+vals[max(0,min(pstar,len(vals)-1))]
  for index,row in enumerate(data['xenoPetAwakening']):
   count=sum(1 for name in XENO_NAMES if _num(stars.get(name))>index)
   vals=row.get('values',[]) or []
   if vals:_add(out,{row['stat']:vals[max(0,min(count,len(vals)-1))]})
  for name in XENO_NAMES:_add(out,_threshold((data['pets'].get(name) or {}).get('globalStars'),_num(stars.get(name))))
  _collectible_set_bonus(profile,out)
  dmg=(definition.get('damage') or {}).get(str(star),(definition.get('damage') or {}).get(star,0))
  chance=max(0,min(100,out.get('xenoResChance',0)));res=max(0,out.get('xenoResDamage',0));duration=max(0,min(100,out.get('xenoResDuration',0)))
  out['xenoResMultiplier']=chance*res*(4+duration)/500
  out['xenoDamage']=_num(dmg)*SIO_DIRECT_DAMAGE_COEFFICIENTS[active]*(max(0,out.get('xenoSyncRate',0))/100)*((_num(out.get('xenoSkillDamage'))+100)/100)
 detail['effects']=dict(out)
 return {'stats':out,'detail':detail,'warnings':[]}
