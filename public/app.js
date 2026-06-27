const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const tools = [
  { id: "global", group: "Core", icon: "🧠", name: "Global Plan", status: "working draft", desc: "Ranks the next best account move using simple DPS-first rules.", fields: [
    ["chapter", "Chapter", "number", 126], ["gems", "Gems", "number", 51000], ["cores", "Relic cores", "number", 2], ["crystals", "Awakening crystals", "number", 49], ["goal", "Goal", "select", "Max DPS", ["Max DPS", "AFK / Low Effort", "Boss Damage", "Gem Efficiency"]], ["blocker", "Biggest blocker", "select", "Relic cores", ["Relic cores", "Pet copies", "Tech parts", "Gems", "Survivor shards"]]
  ], calc: globalCalc, notes: ["DPS is weighted above HP.", "Scarce resources are protected unless they unlock a clear breakpoint.", "This is starter logic; later it should call your Python optimizer data."] },
  { id: "event", group: "Economy", icon: "🎟️", name: "Event Value", status: "working", desc: "Checks if an event spend is worth it from rewards and gem cost.", fields: [
    ["gemsSpent", "Gems to spend", "number", 12000], ["keysUsed", "Keys used", "number", 80], ["relicCores", "Relic cores gained", "number", 1], ["sChests", "S/SS chest value", "number", 1], ["shards", "Useful shards", "number", 30], ["junk", "Junk reward penalty", "number", 15]
  ], calc: eventCalc, notes: ["This is not exact event math yet.", "Use it to compare rough value before spending gems.", "High-value rewards are cores, useful chests, shards, and rare upgrade blockers."] },
  { id: "gear", group: "Gear", icon: "⚔️", name: "Gear Compare", status: "working", desc: "Compares two upgrades by damage gain, cost, and confidence.", fields: [
    ["aName", "Option A name", "text", "SS Belt upgrade"], ["aGain", "Option A DPS gain %", "number", 14], ["aCost", "Option A cost score", "number", 8], ["bName", "Option B name", "text", "Pet level push"], ["bGain", "Option B DPS gain %", "number", 9], ["bCost", "Option B cost score", "number", 4]
  ], calc: compareCalc, notes: ["Cost score is rough: 1 cheap, 10 very expensive.", "Higher gain per cost wins.", "Later this should use exact gear tables."] },
  { id: "pet", group: "Pets", icon: "🦅", name: "Pet Planner", status: "working", desc: "Decides whether pet leveling/awakening is efficient right now.", fields: [
    ["petLevel", "Current pet level", "number", 78], ["target", "Target level", "number", 100], ["cookies", "Cookies owned", "number", 65000], ["copies", "Useful pet copies", "number", 0], ["crystals", "Pet awakening crystals", "number", 49], ["petType", "Main pet", "select", "Eagle", ["Eagle", "Crab", "Rex", "Croaky", "Other"]]
  ], calc: petCalc, notes: ["Level 100 is treated as an important target.", "Awakening is blocked if copies are missing.", "Crystals alone are not enough if the pet copies are missing."] },
  { id: "tech", group: "Tech", icon: "🔧", name: "Tech / Resonance", status: "working", desc: "Checks if tech progress should be pushed or saved.", fields: [
    ["mainRarity", "Main tech rarity", "select", "Legendary", ["Epic", "Legendary", "Eternal"]], ["assistCount", "Assist tech pieces", "number", 2], ["chips", "Resonance chips", "number", 1200], ["isTwinborn", "Twinborn target?", "select", "Yes", ["Yes", "No"]], ["pairReady", "Both pair techs ready?", "select", "No", ["Yes", "No"]], ["slotMatch", "Chip slot matches?", "select", "Yes", ["Yes", "No"]]
  ], calc: techCalc, notes: ["Resonance rules are slot/type sensitive.", "Twinborn needs the paired techs ready.", "This screen is for blockers first, math second."] },
  { id: "cores", group: "Gear", icon: "🧩", name: "Relic Core Planner", status: "working", desc: "Helps decide whether to spend or save relic cores.", fields: [
    ["cores", "Relic cores owned", "number", 2], ["nextCost", "Next upgrade core cost", "number", 1], ["gain", "Expected DPS gain %", "number", 12], ["altGain", "Best non-core gain %", "number", 7], ["futureNeed", "Future SS need", "select", "High", ["Low", "Medium", "High"]]
  ], calc: coreCalc, notes: ["Relic cores are treated as rare.", "A small gain can still win if it unlocks a major chain.", "Future SS need increases the save recommendation."] },
  { id: "collect", group: "Economy", icon: "💠", name: "Collectibles", status: "working", desc: "Ranks collectible shard spending by damage value.", fields: [
    ["shards", "Shard amount", "number", 80], ["damage", "Damage bonus %", "number", 3], ["set", "Completes set?", "select", "No", ["Yes", "No"]], ["cost", "Cost score", "number", 5], ["late", "Late-game account?", "select", "No", ["Yes", "No"]]
  ], calc: collectibleCalc, notes: ["Collectibles get better when they complete sets or add real damage.", "Random shard spending is weak if no set or damage breakpoint is reached."] },
  { id: "chapter", group: "Modes", icon: "🏃", name: "Chapter Push", status: "working", desc: "Checks whether pushing chapters is worth it for patrol and progress.", fields: [
    ["chapter", "Current chapter", "number", 126], ["stuck", "Are you stuck?", "select", "No", ["Yes", "No"]], ["clearTime", "Clear time minutes", "number", 12], ["patrolGain", "Estimated patrol gain %", "number", 4], ["effort", "Effort level", "select", "Low", ["Low", "Medium", "High"]]
  ], calc: chapterCalc, notes: ["Chapter pushing is worth more when it unlocks patrol value.", "If effort is high and gain is small, save upgrades first."] },
  { id: "echo", group: "Modes", icon: "👹", name: "Enders Echo", status: "working", desc: "Separate single-target scoring from chapter-clear scoring.", fields: [
    ["bossGain", "Boss DPS gain %", "number", 11], ["clearGain", "Chapter clear gain %", "number", 4], ["manual", "Manual skill needed", "select", "Medium", ["Low", "Medium", "High"]], ["duration", "Useful uptime %", "number", 70], ["cost", "Cost score", "number", 6]
  ], calc: echoCalc, notes: ["Echo values boss damage and uptime more than lazy clearing.", "High manual effort lowers value if your style is AFK."] },
  { id: "confidence", group: "Data", icon: "🧾", name: "Source Confidence", status: "working", desc: "Labels recommendation quality based on data completeness.", fields: [
    ["known", "Known data points", "number", 8], ["missing", "Missing data points", "number", 3], ["conflicts", "Conflicts", "number", 1], ["tested", "Tested in optimizer?", "select", "Yes", ["Yes", "No"]]
  ], calc: confidenceCalc, notes: ["This should appear beside every recommendation later.", "Missing or conflicting data should reduce confidence, not pretend certainty."] }
];

let active = tools[0].id;
const profile = { chapter: 126, gems: 51000, cores: 2, crystals: 49 };

function n(id){ return Number(($(`[name='${id}']`)?.value || 0)); }
function v(id){ return $(`[name='${id}']`)?.value || ""; }
function scoreLabel(score){ return score >= 80 ? "Excellent" : score >= 60 ? "Good" : score >= 40 ? "Okay" : "Weak"; }
function money(x){ return Number(x || 0).toLocaleString("en-US"); }

function globalCalc(){
  const gems=n("gems"), cores=n("cores"), crystals=n("crystals"), chapter=n("chapter"), blocker=v("blocker"), goal=v("goal");
  const saveScore = gems > 30000 ? 25 : 10;
  const coreScore = blocker === "Relic cores" && cores > 0 ? 35 : 15;
  const petScore = blocker === "Pet copies" || crystals > 40 ? 25 : 12;
  const total = Math.min(100, 35 + saveScore + coreScore + petScore + (chapter > 100 ? 5 : 0));
  return { score: total, rows: [
    ["1", blocker === "Relic cores" ? "Check SS / relic core upgrade first" : "Fix your biggest blocker first", `Goal: ${goal}. Current blocker: ${blocker}.`],
    ["2", gems > 30000 ? "Do not spend gems blindly" : "Start saving gems", `${money(gems)} gems means event value needs to be compared before spending.`],
    ["3", crystals > 40 ? "Pet awakening crystals are important but check copies" : "Pet progress is not the main push yet", `${crystals} crystals available.`]
  ]};
}

function eventCalc(){
  const value = n("relicCores")*45 + n("sChests")*22 + n("shards")*.55 + n("keysUsed")*.18 - n("junk") - n("gemsSpent")/900;
  return { score: Math.max(0, Math.min(100, Math.round(value+35))), rows: [
    ["Value", value > 35 ? "Spend looks strong" : value > 15 ? "Maybe spend only to breakpoint" : "Probably save", `Estimated event value score: ${value.toFixed(1)}.`],
    ["Reason", "Cores and useful chests carry the score", "Junk rewards and big gem costs lower it."],
    ["Rule", "Do not chase weak milestones", "Only push if the next reward is a real account upgrade."]
  ]};
}

function compareCalc(){
  const a=n("aGain")/Math.max(1,n("aCost")), b=n("bGain")/Math.max(1,n("bCost"));
  const win = a >= b ? v("aName") : v("bName");
  return { score: Math.round(Math.max(a,b)*20), rows: [
    ["Winner", win, `Option A value ${a.toFixed(2)} vs Option B value ${b.toFixed(2)}.`],
    ["Logic", "Damage per cost wins", "Use this until exact item tables are connected."],
    ["Caution", "Cost score is manual", "Bad cost estimates will give bad rankings."]
  ]};
}

function petCalc(){
  const levels=Math.max(0,n("target")-n("petLevel"));
  const need=levels*2500;
  const enough=n("cookies")>=need;
  const awake=n("crystals")>=40 && n("copies")>0;
  const score=(enough?35:10)+(awake?35:10)+(n("target")>=100?20:5);
  return { score, rows: [
    ["Leveling", enough ? "Cookies look enough for target" : "Need more cookies", `Rough cookie need: ${money(need)}.`],
    ["Awakening", awake ? "Awakening may be available" : "Awakening blocked", "Crystals plus useful pet copies are both needed."],
    ["Pet", v("petType"), "Compare pet upgrades against gear and tech before spending."]
  ]};
}

function techCalc(){
  const legendary=v("mainRarity")!=="Epic";
  const twin=v("isTwinborn")==="Yes";
  const ready=v("pairReady")==="Yes";
  const slot=v("slotMatch")==="Yes";
  const score=(legendary?25:5)+(slot?25:0)+(twin&&ready?35:twin?10:20)+Math.min(15,n("chips")/150);
  return { score: Math.round(score), rows: [
    ["Rarity", legendary ? "Main tech can start serious planning" : "Rarity is too low", `Current rarity: ${v("mainRarity")}.`],
    ["Twinborn", twin ? (ready ? "Pair looks ready" : "Pair is not ready") : "Normal tech path", "Twinborn needs both paired techs ready."],
    ["Chips", slot ? "Slot matches" : "Wrong slot warning", `${n("chips")} chips entered.`]
  ]};
}

function coreCalc(){
  const can=n("cores")>=n("nextCost");
  const advantage=n("gain")-n("altGain");
  const savePenalty=v("futureNeed")==="High"?18:v("futureNeed")==="Medium"?8:0;
  const score=(can?45:10)+advantage*3-savePenalty;
  return { score: Math.round(Math.max(0,Math.min(100,score))), rows: [
    ["Core spend", can ? "You can afford it" : "Not enough cores", `${n("cores")} owned / ${n("nextCost")} needed.`],
    ["Gain check", advantage>3 ? "Core upgrade beats alternative" : "Alternative may be better", `${advantage}% advantage over non-core option.`],
    ["Future need", v("futureNeed"), "High future need means saving cores gets more weight."]
  ]};
}

function collectibleCalc(){
  const score=n("damage")*12+(v("set")==="Yes"?25:0)+(v("late")==="Yes"?10:0)-n("cost")*3;
  return { score: Math.round(Math.max(0,Math.min(100,score))), rows: [
    ["Spend call", score>55 ? "Worth considering" : "Do not force it", `${n("damage")}% damage bonus entered.`],
    ["Set bonus", v("set")==="Yes" ? "Set completion boosts value" : "No set completion", "Set completion matters more than random shard usage."],
    ["Timing", v("late")==="Yes" ? "Late-game value increased" : "May be early", "Collectibles get stronger later."]
  ]};
}

function chapterCalc(){
  const score=n("patrolGain")*10-(v("effort")==="High"?20:v("effort")==="Medium"?8:0)+(v("stuck")==="No"?18:0)-(n("clearTime")>15?8:0);
  return { score: Math.round(Math.max(0,Math.min(100,score))), rows: [
    ["Push call", score>50 ? "Push chapters" : "Upgrade first", `${n("patrolGain")}% patrol gain estimate.`],
    ["Effort", v("effort"), "Low effort push is better for your preferred style."],
    ["Status", v("stuck")==="Yes" ? "You are stuck, upgrade before forcing" : "Not stuck, push is reasonable", `Clear time: ${n("clearTime")} minutes.`]
  ]};
}

function echoCalc(){
  const uptime=n("duration")/100;
  const manualPenalty=v("manual")==="High"?18:v("manual")==="Medium"?8:0;
  const score=n("bossGain")*5*uptime+n("clearGain")-n("cost")*2-manualPenalty+30;
  return { score: Math.round(Math.max(0,Math.min(100,score))), rows: [
    ["Echo value", score>60 ? "Good Echo-focused upgrade" : "Not great for Echo", `${n("bossGain")}% boss gain at ${n("duration")}% uptime.`],
    ["Manual effort", v("manual"), "High manual effort lowers score if you prefer AFK."],
    ["Separate logic", "Do not use chapter ranking here", "Boss scoring needs its own plan."]
  ]};
}

function confidenceCalc(){
  const total=n("known")+n("missing")+n("conflicts");
  const knownRatio=total? n("known")/total : 0;
  const score=knownRatio*100-n("conflicts")*12-(v("tested")==="No"?15:0);
  return { score: Math.round(Math.max(0,Math.min(100,score))), rows: [
    ["Confidence", score>70 ? "High enough to show" : score>45 ? "Show with warning" : "Needs review", `${n("known")} known, ${n("missing")} missing, ${n("conflicts")} conflicts.`],
    ["Testing", v("tested"), "Untested logic should not sound certain."],
    ["Rule", "Confidence must be visible", "Every recommendation should show source quality."]
  ]};
}

function groupTools(list){
  return list.reduce((acc,t)=>{(acc[t.group] ||= []).push(t); return acc;},{});
}

function renderSidebar(){
  const q=($("#search").value||"").toLowerCase();
  const filtered=tools.filter(t=>`${t.name} ${t.group} ${t.desc}`.toLowerCase().includes(q));
  const groups=groupTools(filtered);
  $("#groups").innerHTML=Object.keys(groups).map(g=>`<div class="group"><div class="group-title">${g}</div>${groups[g].map(t=>`<button class="tool-btn ${t.id===active?"active":""}" data-id="${t.id}" type="button"><span class="tool-ico">${t.icon}</span><span><span class="tool-name">${t.name}</span><span class="tool-mini">${t.status}</span></span><span>›</span></button>`).join("")}</div>`).join("") || `<div class="empty">No tools found.</div>`;
  $$(".tool-btn").forEach(b=>b.addEventListener("click",()=>loadTool(b.dataset.id)));
}

function fieldHtml(f){
  const [id,label,type,value,options]=f;
  if(type==="select") return `<div class="field"><label for="${id}">${label}</label><select id="${id}" name="${id}">${options.map(o=>`<option ${o===value?"selected":""}>${o}</option>`).join("")}</select></div>`;
  return `<div class="field"><label for="${id}">${label}</label><input id="${id}" name="${id}" type="${type}" value="${value}"></div>`;
}

function loadTool(id){
  active=id;
  const t=tools.find(x=>x.id===id);
  $("#toolCategory").textContent=t.group;
  $("#toolTitle").textContent=t.name;
  $("#toolDescription").textContent=t.desc;
  $("#toolStatus").textContent=t.status;
  $("#toolForm").innerHTML=`<div class="form-grid">${t.fields.map(fieldHtml).join("")}<div class="calc-actions"><button class="btn" type="submit">Calculate</button><button class="btn ghost" type="button" id="resetTool">Reset</button></div></div>`;
  $("#notesBox").innerHTML=`<ul>${t.notes.map(n=>`<li>${n}</li>`).join("")}</ul>`;
  $("#toolForm").onsubmit=(e)=>{e.preventDefault();calculate();};
  $("#resetTool").onclick=()=>loadTool(active);
  $$("#toolForm input,#toolForm select").forEach(el=>el.addEventListener("input",calculate));
  renderSidebar();
  calculate();
}

function calculate(){
  const t=tools.find(x=>x.id===active);
  const out=t.calc();
  const score=Math.round(Math.max(0,Math.min(100,out.score||0)));
  $("#scoreBadge").textContent=`${score}/100 ${scoreLabel(score)}`;
  $("#resultBox").innerHTML=`<div class="big-number">${score}</div>${out.rows.map(r=>`<div class="result-line priority"><span class="rank">${r[0]}</span><div><strong>${r[1]}</strong><span>${r[2]}</span></div></div>`).join("")}`;
}

function copyResults(){
  const text=`${$("#toolTitle").textContent}\n${$("#scoreBadge").textContent}\n${$("#resultBox").innerText}`;
  navigator.clipboard?.writeText(text);
  $("#copyBtn").textContent="Copied";
  setTimeout(()=>$("#copyBtn").textContent="Copy results",900);
}

function loadSample(){
  Object.entries(profile).forEach(([k,val])=>{const el=$(`[name='${k}']`); if(el) el.value=val;});
  calculate();
}

$("#search").addEventListener("input",renderSidebar);
$("#copyBtn").addEventListener("click",copyResults);
$("#sampleBtn").addEventListener("click",loadSample);
loadTool(active);
