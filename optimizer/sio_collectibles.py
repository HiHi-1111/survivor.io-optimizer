"""sIO global collectible, collection-set and custom-set assembly."""
from __future__ import annotations
import math
from typing import Any,Mapping
from optimizer.sio_collectible_data import SIO_COLLECTIBLE_DATA

GLOBAL_COLLECTIBLE_NAMES=['Human Genome Mapping','Book of Ancient Wisdom','Immortal Lucky Coin','Instellar Transition Matrix Design','Angelic Tear Crystal',"Unicorn's Horn",'Otherworld Key','Starcore Diamond','High-Lat Energy Cube','Void Bloom','Eye of True Vision','Life Hourglass','Nano-Mimetic Mask','Dice of Destiny','Dimension Foil','Mental Sync Helm','Atomic Mech','Time Essence Bottle','Dragon Tooth','Hyper Neuron','Cyber Totem','Clone Mirror','Dreamscape Puzzle','Gene Splicer','Memory Editor','Temporal Rewinder','Spatial Rewinder','Holodream Fluid','Dark Matter Construct','Timeline Cube','Omni-Symbiote',"Prophet's Tarot",'Aquarius Starlight','Pisces Starlight','Aries Starlight','Taurus Starlight','Golden Cutlery','Old Medical Book',"Savior's Memento",'Safehouse Map','Lucky Charm',"Scientific Luminary's Journal",'Super Circuit Board','Mystical Halo','Tablet of Epics','Primordial War Drum','Flaming Plume','Astral Dewdrop','Nuclear Battery','Plasma Sword','Golden Horn','Elemental Ring','Anti-Gravity Device','Hydraulic Flipper','Superhuman Pill','Comms Conch','Mini Dyson Sphere','Micro Artificial Sun','Klein Bottle','Antiparticle Gourd','Wildfire Furnace','Infinity Score','Cosmic Compass','Wormhole Detector','Shuttle Capsule','Neurochip','Star-Rail Passenger Card','Portable Mech Case','Geocore Orb','Aquacore Orb','Pyrocore Orb','Aerocore Orb','Gemini Starlight','Cancer Starlight','Leo Starlight','Virgo Starlight']

def _num(v:Any,d=0.0):
 try:x=float(v)
 except (TypeError,ValueError):return d
 return x if math.isfinite(x) else d

def _add(o,src,scale=1.0):
 for k,v in (src or {}).items():
  x=_num(v)*scale
  if x:o[str(k)]=o.get(str(k),0)+x

def _threshold(table,level):
 chosen=None
 for n,v in zip((table or {}).get('nums',[]) or [],(table or {}).get('vals',[]) or []):
  if level<_num(n):break
  chosen=v
 return chosen or {}

def _unwrap(v):return v.get('data') if isinstance(v,Mapping) and isinstance(v.get('data'),Mapping) else v

def collectible_state(profile):
 sio=profile.get('sio_ce') if isinstance(profile.get('sio_ce'),Mapping) else {}
 raw=_unwrap(sio.get('collectibles') or profile.get('collectibles') or {})
 if isinstance(raw,Mapping) and isinstance(raw.get('owned'),Mapping):raw=raw['owned']
 return {str(k):({'stars':_num(v.get('stars'))} if isinstance(v,Mapping) else {'stars':_num(v)}) for k,v in raw.items()} if isinstance(raw,Mapping) else {}

def _progress(names,cols):
 vals=[_num((cols.get(n) or {}).get('stars')) for n in names]
 return {'gold':sum(min(5,x) for x in vals),'red':sum(max(0,x-5) for x in vals),'total':sum(vals),'goldEach':min(vals) if vals else 0,'redEach':min((x-5 for x in vals),default=0)}

def _apply_sets(out,sets,cols,detail):
 for name,d in (sets or {}).items():
  p=_progress(d.get('collectibles',[]) or [],cols);effects={}
  for typ,thresholds in (d.get('stars',{}) or {}).items():
   for threshold,e in sorted(((float(k),v) for k,v in (thresholds or {}).items())):
    if p.get(typ,0)>=threshold:_add(out,e);_add(effects,e)
  detail[name]={'progress':p,'effects':effects}

def assemble_sio_collectible_stats(profile:Mapping[str,Any])->dict[str,Any]:
 data=SIO_COLLECTIBLE_DATA;cols=collectible_state(profile)
 sio=profile.get('sio_ce') if isinstance(profile.get('sio_ce'),Mapping) else {}
 upgraded=set(sio.get('upgraded_collectibles',profile.get('upgraded_collectibles',[])) or [])
 out={};detail={'collectibles':{},'sets':{},'customSets':{}}
 for name in GLOBAL_COLLECTIBLE_NAMES:
  stars=_num((cols.get(name) or {}).get('stars'));effects=_threshold((data['collectibles'].get(name) or {}).get('stars'),stars)
  scale=1.33 if name in upgraded else 1.0;_add(out,effects,scale)
  if effects:detail['collectibles'][name]={'stars':stars,'scale':scale,'effects':dict(effects)}
 _apply_sets(out,data['sets'],cols,detail['sets'])
 raw=_unwrap(sio.get('customSets') or profile.get('customSets') or {})
 if isinstance(raw,Mapping):
  for index,(_,state) in enumerate(raw.items()):
   if not isinstance(state,Mapping):continue
   definition=data['customSets'].get(str(index),{})
   names=[x for x in (state.get('collectibles',[]) or []) if x and x!='None']
   depth=len(names);effects={}
   e=_threshold(definition.get('Legend'),depth);_add(out,e);_add(effects,e)
   if depth==definition.get('size'):
    level=int(_num(state.get('level')));advanced=sum(_num((cols.get(n) or {}).get('stars')) for n in names[:level])
    e=_threshold(definition.get('advanced'),advanced);_add(out,e);_add(effects,e)
   else: advanced=0
   detail['customSets'][str(index)]={'depth':depth,'advancedStars':advanced,'effects':effects}
 return {'stats':out,'detail':detail,'collectibles':cols}
