const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const scenarios = ["LME Expedition Phase", "LME Battle Phase", "Ender's Echo"];
let selectedScenario = scenarios[0];

const gearBySlot = {
  Weapon: ["SS Starforged Havoc", "Twin Lance", "Kunai", "Katana", "Baseball Bat", "Shotgun", "Revolver", "Lightchaser", "Void Power", "Sword of Disorder", "Army Rifle", "Other Weapon"],
  Necklace: ["SS Judgement Necklace", "Eternal Necklace", "Voidwaker Emblem", "Chaos Necklace", "Trendy Charm", "Metal Neckguard", "Army Nameplate", "Emerald Pendant", "Bone Pendant", "Other Necklace"],
  Gloves: ["SS Gloves", "Eternal Gloves", "Voidwaker Handguards", "Chaos Gauntlets", "Army Gloves", "Fingerless Gloves", "Leather Gloves", "Shiny Wristguard", "Protective Gloves", "Other Gloves"],
  Armor: ["SS Armor", "Eternal Suit", "Voidwaker Windbreaker", "Armor of Quietus", "Full Metal Suit", "Protective Suit", "Traveler Jacket", "Carapace", "Army Uniform", "Other Armor"],
  Belt: ["SS Belt", "Eternal Belt", "Voidwaker Sash", "Twisting Belt", "Stylish Belt", "Waist Sensor", "Broad Waistguard", "Army Belt", "Leather Belt", "Other Belt"],
  Boots: ["SS Boots", "Eternal Boots", "Voidwaker Treads", "Shoes of Confusion", "Light Runners", "Highboots", "Layered Snowshoes", "Prosthetic Legs", "Army Boots", "Other Boots"]
};

const slotGlyph = { Weapon:"⚔", Necklace:"◉", Gloves:"✊", Armor:"⬢", Belt:"◎", Boots:"◒" };
const itemSystems = ["Normal", "S Grade", "SS", "Astral Forge", "Cosmic Cast", "Xeno", "Relic Core", "Wishlist", "Selectors", "Designs", "Merge/Fodder", "Salvage"];
const techTop = [
  ["Drone Mode","▣",3000],["Drill Shot Mode","◎",3000],["Durian Mode","◌",3000],["Lightning Mode","⌁",0],["Guardian Mode","⛨",0],["Brick Mode","▤",0],["Molotov","◍",2100],["Rocket","▰",0],["Drone","◈",0],["Drill","◇",0]
];
const techSkills = [
  ["Drone","✈",-49.54,true],["Drill Shot","➤",-36.92,true],["Durian","✹",-31.32,true],["Molotov","▣",-23.93,true],["Rocket","➹",0,true],
  ["Energy Cube","▤",-28.25,true],["HP Bullet","▯",-37.5,true],["Exo Bracer","◔",-1.12,true],["Ammo Thruster","◉",-0.08,false],["HE Fuel","▱",-8.43,false]
];
const survivorFeatured = [["Raphael","R",5],["Robot Core","Ω",6],["Aqua Scout","A",6]];
const survivorNames = ["Yang","Metallia","King","Worm","Catnips","Common","Tsukuyomi","Wesson","Yelena","Spongebob","Squidward","Raphael","Leonardo","Donatello","April","Splinter","Patrick","Sandy","Squid Guard","Arcade Hero","Void Cadet","Cyber Medic","Green Ranger","Crimson Agent","Gary","Other A","Other B","Other C"];
const customSetNames = ["Custom Collection Set #1", "Custom Collection Set #2", "Custom Collection Set #3", "Custom Collection Set #4"];
const collectibleGlyphs = ["⚙","◆","★","◈","✦","✧","⌬","◇","⬟","☼","◉","◌","▣","▤","▥","▦","▧","▨","▩","✚","✹","✺","✸","✷","✶","✵","✴","✳","✲","✱","✰","✪","✩","☄","☽","☀","☁","☂","☃","☯","♜","♞","♟","♛","♝","♚","⚗","⚒","⚔","⚕","⚚","⚜","⚛","⚡","⛨","⛭","⛯","✿","❖","⬢","⬡","⬠","⬟","⬞","⬝","◆","◇","◈","◍","◎","●","○","◐","◑","◒","◓","◔","◕","◖","◗","◦","◧","◨","◩","◪","◫","◬","◭","◮","◯","☉","☊","☋","☌","☍","☏","☢","☣","☤","☥","☬","☮"];
const evoSkills = [["Expose Weakness","☼"],["Viva la Materia","◈"],["Overreaction","◔"],["Watchmaker","➜"]];
const lunar = [["ATK", "⚔", "0%"],["Shield", "⛨", "0%"],["Cart", "▣", "0%"],["Chest", "▤", "0%"],["Burst", "✹", "0%"],["Crit", "✦", "0%"],["Tower", "▥", "0%"],["Crystal", "◆", "0%"]];
const pets = [["Main pet: Rex","🐶",6],["Motivation","⚙",5],["Inspiration","✹",5],["Encouragement","⬆",5],["Battle Lust","✦",5],["Gary","🐌",4]];
const mounts = [["Electric Scooter","◉"],["Tech Hoverboard","▰"],["Doomsteed","♞"]];

function stars(count, total = 6) {
  return `<span class="stars">${Array.from({length:total},(_,i)=>`<span class="${i<count?'star-on':'star-off'}">★</span>`).join("")}</span>`;
}
function options(list, selected) { return list.map(x => `<option ${x === selected ? "selected" : ""}>${x}</option>`).join(""); }
function miniDots() { return `<div class="mini-badges"><span class="mini-dot" style="background:#2f8cff">☄</span><span class="mini-dot" style="background:#e63876">▣</span><span class="mini-dot" style="background:#9365ff">◉</span></div>`; }
function icon(cls, glyph, badge="↯") { return `<div class="${cls}">${glyph}<span class="icon-badge">${badge}</span></div>`; }

function renderScenario() {
  $("#scenario-options").innerHTML = scenarios.map(s => `<label class="radio-pill ${s===selectedScenario?'active':''}"><span class="radio-dot"></span>${s}</label>`).join("");
  $$(".radio-pill").forEach((el,i)=>el.addEventListener("click",()=>{selectedScenario=scenarios[i];renderScenario();calculateResult();}));
}
function renderItems() {
  $("#item-support-strip").innerHTML = itemSystems.map(x=>`<span class="support-chip">${x}</span>`).join("");
  $("#gear-grid").innerHTML = Object.keys(gearBySlot).map((slot,i)=>{
    const selected = gearBySlot[slot][0];
    const rarity = i%3===0?'rarity-cosmic':i%3===1?'rarity-legendary':'rarity-epic';
    return `<article class="gear-card ${rarity}">
      ${icon('gear-icon', slotGlyph[slot], '+15')}
      <div class="gear-info"><div class="gear-title">${selected}</div><select class="gear-select" data-slot="${slot}">${options(gearBySlot[slot],selected)}</select>${stars(i<2?5:4)}${miniDots()}</div>
    </article>`;
  }).join("");
  $$(".gear-select").forEach(sel=>sel.addEventListener("change",e=>{e.target.closest('.gear-card').querySelector('.gear-title').textContent=e.target.value;calculateResult();}));
}
function renderTech() {
  $("#tech-top-grid").innerHTML = techTop.map(t=>`<div class="tech-top-card"><div class="tech-icon">${t[1]}</div><div>${t[0]}</div><div class="green-value">⬢ ${t[2]}</div></div>`).join("");
  $("#tech-skill-grid").innerHTML = techSkills.map(t=>`<div class="skill-card"><span class="check-tag">${t[3]?'✓':'🔒'}</span>${icon('card-icon',t[1],'') }<div>${t[0]}</div><div class="delta ${t[2]===0?'good':'bad'}">${t[2]}%</div></div>`).join("");
}
function renderSurvivors() {
  $("#featured-survivors").innerHTML = survivorFeatured.map(s=>`<div class="featured-card">${icon('card-icon',s[1],'↯')}<div>${s[0]}</div>${stars(s[2])}</div>`).join("");
  $("#survivor-grid").innerHTML = survivorNames.map((name,i)=>`<div class="survivor-card">${icon('card-icon',name[0] || 'S','') }${stars((i%7)+1,8)}<div class="level-badge">130</div></div>`).join("");
}
function renderCustomSets() {
  $("#custom-set-list").innerHTML = customSetNames.map((name,idx)=>`<div class="set-row"><strong>${name}</strong><div class="set-icons">${Array.from({length:8},(_,i)=>`<div class="set-icon">▣</div>`).join("")}</div></div>`).join("");
}
function renderCollectibles() {
  $("#collectibles-grid").innerHTML = collectibleGlyphs.map((g,i)=>`<div class="collectible-card"><span class="corner-badge">${(i%10)+1}</span><div class="collectible-icon">${g}</div>${stars((i%5)+1,5)}</div>`).join("");
}
function renderEvo() { $("#evo-grid").innerHTML = evoSkills.map(s=>`<div class="evo-card"><div class="evo-icon">${s[1]}</div><div>${s[0]}</div></div>`).join(""); }
function renderLunar() { $("#lunar-grid").innerHTML = lunar.map(l=>`<div class="lunar-cell"><div class="lunar-icon">${l[1]}</div><select>${["0%","5%","10%","12%","15%","18%","20%"].map(x=>`<option ${x===l[2]?'selected':''}>${x}</option>`).join("")}</select></div>`).join(""); }
function renderPets() { $("#pets-grid").innerHTML = pets.map(p=>`<div class="pet-card"><div class="pet-icon">${p[1]}</div><div>${p[0]}</div>${stars(p[2],6)}<select><option>Super</option><option>Legend</option><option>Assist</option></select></div>`).join(""); }
function renderMounts() { $("#mounts-grid").innerHTML = mounts.map((m,i)=>`<div class="mount-card"><div>${m[0]}</div><div class="mount-art">${m[1]}</div><label class="toggle-line"><input type="checkbox" ${i===0?'checked':''}> ${i===0?'Electric Hover':i===1?'Gravity Drive':'Jet Strider'}</label>${stars(i===0?3:2,5)}</div>`).join(""); }

function calculateResult() {
  const base = Number($("#base-atk")?.value || 0);
  const finalAtk = Number($("#final-atk")?.value || 0);
  const selectedGear = $$(".gear-select").filter(x=>x.value.includes("SS") || x.value.includes("Void") || x.value.includes("Eternal")).length;
  const scenarioMult = selectedScenario.includes("Echo") ? 1.22 : selectedScenario.includes("Battle") ? 1.12 : 1.05;
  const score = Math.round((base + finalAtk + 10000) * scenarioMult * (1 + selectedGear * .18) * 1048576);
  $("#total-damage").textContent = score.toLocaleString("en-US");
}
function exportProfile() {
  const payload = { scenario:selectedScenario, gear: $$(".gear-select").map(x=>({slot:x.dataset.slot,item:x.value})), atk:{base:$("#base-atk").value, final:$("#final-atk").value}, supported:{gearSlots:Object.keys(gearBySlot), itemSystems, tech:techTop.map(t=>t[0]), survivors:survivorNames.length, collectibles:collectibleGlyphs.length, pets:pets.length, mounts:mounts.length} };
  navigator.clipboard?.writeText(JSON.stringify(payload,null,2));
}
function bind() {
  $("#export-profile")?.addEventListener("click", exportProfile);
  $("#share-profile")?.addEventListener("click", exportProfile);
  $("#reset-profile")?.addEventListener("click",()=>location.reload());
  ["base-atk","final-atk","total-atk","designs"].forEach(id=>$("#"+id)?.addEventListener("input",calculateResult));
}
function init(){renderScenario();renderItems();renderTech();renderSurvivors();renderCustomSets();renderCollectibles();renderEvo();renderLunar();renderPets();renderMounts();bind();calculateResult();}
init();