function generateGearCandidates(profile){
  var out=[];
  var defs=self.SIO_ITEMS||{};
  var entries=((profile.itemsOptimizer||{}).entries)||{};
  Object.keys(defs).forEach(function(name){
    var def=defs[name];
    var entry=entries[name]||{state:'enabled',min:{},max:{}};
    if(entry.state==='disabled')return;

    if(entry.mode==='simple'||entry.simple){
      var cur=Number((entry.simple&&entry.simple.current)||(entry.min&&entry.min.star)||0)||0;
      var max=Number((entry.simple&&entry.simple.max)||(entry.max&&entry.max.star)||10)||10;
      if(max<=cur)return;
      var best=0.001;
      Object.keys(def.paths||{}).forEach(function(p){best=Math.max(best,Number(def.paths[p].dmgPerLevel)||0)});
      var step=cur+1;
      var gain=self.estimateRelativeGain(profile,best);
      var cost=Math.max(1,step);
      out.push({category:'Gear',itemName:name,current:cur,next:step,action:'Upgrade '+name+' stars '+cur+' -> '+step,reason:'Best next gear-star upgrade from your equipped setup',estimatedGain:gain,cost:{relicCores:cost},efficiency:gain/cost,recommendationType:'add'});
      return;
    }

    Object.keys(def.paths||{}).forEach(function(path){
      var cur2=Number((entry.min||{})[path])||0;
      var max2=Number((entry.max||{})[path])||0;
      if(max2<=cur2)return;
      var step2=cur2+1;
      var gain2=self.estimateRelativeGain(profile,(def.paths[path].dmgPerLevel||0.001));
      var cost2=Math.max(1,step2);
      out.push({category:'Gear',itemName:name,current:cur2,next:step2,action:'Upgrade '+name+' '+cur2+' -> '+step2,reason:'Estimated DPS gain per relic core',estimatedGain:gain2,cost:{relicCores:cost2},efficiency:gain2/cost2,recommendationType:'add'});
    });
  });
  if(out.length===0)out.push({_warning:'No gear upgrade range is enabled. Add your equipment stars first.'});
  return out;
}
self.generateGearCandidates=generateGearCandidates;
