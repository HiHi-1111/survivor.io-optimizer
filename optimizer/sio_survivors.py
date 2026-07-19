"""sIO Survivor, Synergy, Harmony, skill and Evolution Tree assembly."""
from __future__ import annotations
import math
from typing import Any, Mapping
from optimizer.sio_survivor_data import SIO_SURVIVOR_DATA

HERO_ORDER = ["Common","Tsukuyomi","Catnips","Worm","King","Wesson","Yelena","Master Yang","Metalia","Joey","Taloxa","Raphael","April","Donatello","Splinter","Leonardo","Michelangelo","Squidward","Spongebob","Sandy","Patrick","Venato","Nezha","Vulcan"]
ALWAYS_FULL_STAR_HERO = "Vulcan"
SP_RARITY = "SP"
XENO_SYNC_BY_STARS = {7:10.0,8:20.0,10:30.0,12:50.0}
EXPOSED_SCALE = 10.0
JOEY_WEAK_SPOT_SCALE = 0.7
FLASHRIFT_US = 14.75
FLASHRIFT_EFFICIENCY_DIVISOR = 30.0

def _num(v:Any,d:float=0.0)->float:
 try:
  x=float(v)
 except (TypeError,ValueError): return d
 return x if math.isfinite(x) else d

def _add(out:dict[str,float], src:Mapping[str,Any]|None)->None:
 for k,v in (src or {}).items():
  x=_num(v)
  if x: out[str(k)]=out.get(str(k),0.0)+x

def _threshold(table:Mapping[str,Any]|None, level:float)->dict[str,float]:
 if not table:return {}
 chosen=None
 for n,v in zip(table.get("nums",[]) or [],table.get("vals",[]) or []):
  if level<_num(n): break
  chosen=v
 return {str(k):_num(v) for k,v in (chosen or {}).items() if _num(v)}

def _unwrap(v:Any)->Any:
 return v.get("data") if isinstance(v,Mapping) and isinstance(v.get("data"),Mapping) else v

def _meta(profile:Mapping[str,Any])->dict[str,Any]:
 sio=profile.get("sio_ce") if isinstance(profile.get("sio_ce"),Mapping) else {}
 meta={}
 for row in (profile.get("meta"),sio.get("meta")):
  row=_unwrap(row)
  if isinstance(row,Mapping):meta.update(row)
 for key in ("mainHero","main_hero","harmonyL","harmonyR","teamwork","synergy","synergyLevel","clanLevel","withXeno"):
  if key in profile: meta[key]=profile[key]
  if key in sio: meta[key]=sio[key]
 return meta

def hero_state_from_profile(profile:Mapping[str,Any])->dict[str,dict[str,Any]]:
 sio=profile.get("sio_ce") if isinstance(profile.get("sio_ce"),Mapping) else {}
 raw=_unwrap(sio.get("heroes") or profile.get("heroes") or {})
 return {str(k):dict(v) for k,v in raw.items() if isinstance(v,Mapping)} if isinstance(raw,Mapping) else {}

def _harmony_progress(heroes:Mapping[str,Mapping[str,Any]], names:list[str])->dict[str,int]:
 stars=[int(_num((heroes.get(name) or {}).get("stars"))) for name in names]
 gold=sum(min(6,s) for s in stars)
 red=sum(max(0,s-6) for s in stars) if gold==18 else 0
 return {"goldStars":gold,"redStars":red,"leftLevel":math.floor(red/4)+1 if red else 0,"rightLevel":math.floor((red+2)/4) if red else 0}

def assemble_sio_survivor_stats(profile:Mapping[str,Any])->dict[str,Any]:
 data=SIO_SURVIVOR_DATA
 heroes=hero_state_from_profile(profile)
 meta=_meta(profile)
 main=str(meta.get("mainHero") or meta.get("main_hero") or (profile.get("survivor") or {}).get("id") or "None")
 teamwork=[str(x) for x in (meta.get("teamwork") or []) if x and x!="None"]
 synergy=bool(meta.get("synergy",False))
 synergy_level=int(_num(meta.get("synergyLevel")))
 skills_raw=_unwrap((profile.get("sio_ce") or {}).get("skills") if isinstance(profile.get("sio_ce"),Mapping) else None) or _unwrap(profile.get("skills")) or {}
 skills={str(k):bool(v) for k,v in skills_raw.items()} if isinstance(skills_raw,Mapping) else {}
 out:dict[str,float]={}
 detail:dict[str,Any]={"heroes":{},"teamwork":teamwork,"mainHero":main}
 if synergy:
  _add(out,_threshold(data["synergy"],synergy_level))
  out["atkHero"]=out.get("atkHero",0.0)+synergy_level*400
  detail["synergy"]={"level":synergy_level,"effects":_threshold(data["synergy"],synergy_level),"atkHero":synergy_level*400}
 clan=int(_num(meta.get("clanLevel")))
 if clan: out["atkHeroPercent"]=out.get("atkHeroPercent",0.0)+clan+2
 team=set(teamwork)
 if "Taloxa" in team:
  st=int(_num((heroes.get("Taloxa") or {}).get("stars")))
  if (st>=7 and (skills.get("Rocket Mode") or skills.get("Rocket"))) or (st>=8 and skills.get("Laser Mode")) or (st>=10 and (skills.get("Drone Mode") or skills.get("Drone"))): out["lacerationUptime"]=1
 for name in HERO_ORDER:
  state=heroes.get(name) or {}; stars=int(_num(state.get("stars")))
  if not stars:continue
  definition=data["heroes"].get(name,{})
  effects:dict[str,float]={}
  _add(effects,_threshold(definition.get("level"),120 if synergy else _num(state.get("level"))))
  active_scope= name==main or name in team or name==ALWAYS_FULL_STAR_HERO
  _add(effects,_threshold(definition.get("stars"),stars if active_scope else min(stars,5)))
  if name==main:_add(effects,_threshold(definition.get("passives"),stars))
  if bool(meta.get("withXeno")) and name in {"April","Splinter"}:
   val=0
   for threshold,x in XENO_SYNC_BY_STARS.items():
    if stars>=threshold:val=x
   if val:effects["xenoSyncRate"]=effects.get("xenoSyncRate",0)+val
  _add(out,effects);detail["heroes"][name]={"stars":stars,"active_scope":active_scope,"effects":effects}
 if "Raphael" in team or "Michelangelo" in team:out["lacerationUptime"]=out.get("lacerationUptime",0)+.25
 don=int(_num((heroes.get("Donatello") or {}).get("stars")))
 if don and teamwork:
  sp_count=sum(1 for x in teamwork if data["heroes"].get(x,{}).get("rarity")==SP_RARITY)
  if don>=7:out["critRate"]=out.get("critRate",0)+3*sp_count
  if don>=8:
   out["critDamage"]=out.get("critDamage",0)+3*sp_count;out["skillDamage"]=out.get("skillDamage",0)+3*sp_count
  if don>=10:
   out["shieldDamage"]=out.get("shieldDamage",0)+3*sp_count;out["laceration"]=out.get("laceration",0)+3*sp_count
  if don>=12:
   for k in ("poisoned","weakened","chilled"):out[k]=out.get(k,0)+3*sp_count
  detail["donatello_teamwork_sp_count"]=sp_count
 if synergy:
  left=str(meta.get("harmonyL") or "None");right=str(meta.get("harmonyR") or "None")
  hp=_harmony_progress(heroes,[main,left,right])
  _add(out,_threshold((data["harmony"]["level"] or {}).get(left),hp["leftLevel"]))
  _add(out,_threshold((data["harmony"]["level"] or {}).get(right),hp["rightLevel"]))
  _add(out,_threshold(data["harmony"]["stars"],hp["goldStars"]))
  detail["harmony"]={**hp,"left":left,"right":right}
 if "exposedDamage" in out:out["exposedDamage"]*=EXPOSED_SCALE
 if "taloxaOverloadEff" in out:out["taloxaOverloadEff"]*=5
 if "taloxaOverload" in out:
  out["taloxaOverload"]*=out.get("taloxaOverloadEff",0)/100
  out["taloxaBeam"]=(out.get("taloxaBeam",0)/100+1)*out["taloxaOverload"]/10
 if "crimsonBat" in out:out["crimsonBat"]=out["crimsonBat"]/100+1
 if "joeyWeakSpot" in out:out["joeyWeakSpot"]*=JOEY_WEAK_SPOT_SCALE
 if "flashriftRipFinal" in out:
  out["flashriftRip"]=(out["flashriftRipFinal"]+100*FLASHRIFT_US)/650
  out["flashriftRipFinal"]=(out["flashriftRipFinal"]+100)*FLASHRIFT_US*(out.get("joeyWeakSpot",0)/100+1)
 if "flashriftRipEfficiency" in out:out["flashriftRipEfficiency"]/=FLASHRIFT_EFFICIENCY_DIVISOR
 return {"stats":out,"detail":detail,"heroes":heroes,"meta":meta}

def assemble_sio_skill_evo_stats(profile:Mapping[str,Any])->dict[str,Any]:
 sio=profile.get("sio_ce") if isinstance(profile.get("sio_ce"),Mapping) else {}
 skills=_unwrap(sio.get("skills") or profile.get("skills") or {})
 evo=_unwrap(sio.get("evoTree") or profile.get("evoTree") or {})
 out={};detail={"skills":[],"evoTree":[]}
 if isinstance(skills,Mapping):
  for name,enabled in skills.items():
   if enabled:
    _add(out,(SIO_SURVIVOR_DATA["skills"].get(str(name)) or {}).get("stats"));detail["skills"].append(str(name))
 if isinstance(evo,Mapping):
  for name,enabled in evo.items():
   if enabled:
    _add(out,SIO_SURVIVOR_DATA["evoTree"].get(str(name)));detail["evoTree"].append(str(name))
 return {"stats":out,"detail":detail}
