const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const categories = ["All", "Core", "Gear", "Pets", "Tech", "Survivors", "Economy", "Modes", "Data"];

const tools = [
  ["🧠", "Global Upgrade Plan", "Core", "Featured", "Ranks the next best account upgrades across every major system.", ["priority", "all systems", "planning"]],
  ["📥", "Profile Import / Export", "Core", "Needed", "Save and reload account data with a shareable profile file or key.", ["profile", "backup", "share"]],
  ["⚔️", "Main Item Planner", "Gear", "Draft", "Compare main attack items, slot choices, and upgrade paths.", ["main item", "slots", "forge"]],
  ["🛡️", "Equipment Slots", "Gear", "Draft", "Plan necklace, gloves, armor, belt, and boots by slot.", ["necklace", "gloves", "belt"]],
  ["✨", "Astral Forge Planner", "Gear", "Needed", "Track forge costs, copy blockers, and upgrade timing.", ["forge", "copies", "costs"]],
  ["🧩", "SS / Relic Core Planner", "Gear", "Needed", "Compare SS upgrades, relic core bottlenecks, and long-term value.", ["SS", "cores", "upgrade"]],
  ["🦅", "Pet Planner", "Pets", "Draft", "Compare pets, assists, cookies, levels, and account impact.", ["pets", "cookies", "assist"]],
  ["🌟", "Pet Awakening", "Pets", "Needed", "Plan crystals, stars, copies, and awakening timing.", ["awakening", "crystals", "stars"]],
  ["🧬", "Xeno Pet Planner", "Pets", "Later", "Estimate when to save for xeno progress instead of normal pet growth.", ["xeno", "late game", "pets"]],
  ["🔧", "Tech Part Planner", "Tech", "Draft", "Track drone, RPG, molotov, soccer, brick, durian, drill, laser, lightning, guardian, and forcefield.", ["drone", "RPG", "tech"]],
  ["🔗", "Tech Resonance", "Tech", "Needed", "Plan chips, assist parts, restrictions, and resonance value.", ["resonance", "chips", "assist"]],
  ["♊", "Twinborn Tech", "Tech", "Needed", "Compare twinborn pairs, required rarities, and mode restrictions.", ["twinborn", "legendary", "eternal"]],
  ["🥷", "Survivor Planner", "Survivors", "Draft", "Compare survivors, shards, levels, and switch value.", ["Yang", "Metallia", "shards"]],
  ["🔥", "Survivor Awakening", "Survivors", "Needed", "Track awakening stages, shards, blockers, and upgrade value.", ["awakening", "shards", "SP"]],
  ["💠", "Collectible Planner", "Economy", "Draft", "Rank collectible shards, set bonuses, stats, and timing.", ["collectibles", "shards", "sets"]],
  ["🎟️", "Event Value Calculator", "Economy", "Needed", "Decide whether to spend gems, keys, tickets, or event currency.", ["events", "gems", "keys"]],
  ["🏪", "Shop / Exchange Planner", "Economy", "Needed", "Compare shop buys, shard conversion, and resource trades.", ["shop", "exchange", "value"]],
  ["💎", "Gem Spending Guard", "Economy", "Needed", "Protect gems unless a spend gives strong upgrade value.", ["gems", "F2P", "value"]],
  ["🏃", "Chapter Push Planner", "Modes", "Draft", "Plan chapter progress, steamroll, patrol value, and clearing speed.", ["chapters", "patrol", "steamroll"]],
  ["👹", "Enders Echo Planner", "Modes", "Needed", "Create separate single-target plans for Echo-style scoring.", ["EE", "score", "timing"]],
  ["🏛️", "Path of Trials Planner", "Modes", "Needed", "Plan PoT progress, floor pushes, and breakpoint checks.", ["PoT", "floors", "checks"]],
  ["👥", "Clan / Challenge Planner", "Modes", "Later", "Track challenge-specific builds, clan rewards, and alternate setups.", ["clan", "challenge", "rewards"]],
  ["📊", "Formula Viewer", "Data", "Needed", "Show how bonuses combine and which effects matter most.", ["formula", "multipliers", "DPS"]],
  ["🧾", "Source Confidence", "Data", "Needed", "Mark recommendations as confirmed, estimated, missing, or needing review.", ["sources", "confidence", "warnings"]]
].map(([icon, title, category, status, description, tags]) => ({ icon, title, category, status, description, tags }));

let activeCategory = "All";

function statusClass(status) {
  return status === "Featured" ? "green" : status === "Needed" ? "gold" : status === "Later" ? "dim" : "blue";
}

function renderCategories() {
  const strip = $("#category-strip");
  if (!strip) return;
  strip.innerHTML = categories.map((cat) => `<button class="category-btn ${cat === activeCategory ? "active" : ""}" type="button" data-category="${cat}">${cat}</button>`).join("");
  $$(".category-btn").forEach((btn) => btn.addEventListener("click", () => {
    activeCategory = btn.dataset.category;
    renderCategories();
    renderTools();
  }));
}

function renderTools() {
  const list = $("#tool-list");
  if (!list) return;
  const query = ($("#tool-search")?.value || "").toLowerCase().trim();
  const filtered = tools.filter((tool) => {
    const text = `${tool.title} ${tool.category} ${tool.description} ${tool.tags.join(" ")}`.toLowerCase();
    return (activeCategory === "All" || tool.category === activeCategory) && (!query || text.includes(query));
  });
  $("#tool-count").textContent = `${filtered.length} tools shown • ${tools.length} total systems tracked`;
  list.innerHTML = filtered.map((tool) => `
    <article class="tool-row ${tool.status === "Featured" ? "featured" : ""}">
      <div class="tool-icon">${tool.icon}</div>
      <div class="tool-main">
        <div class="tool-title-line"><h3>${tool.title}</h3><span class="pill ${statusClass(tool.status)}">${tool.status}</span></div>
        <p class="tool-description">${tool.description}</p>
        <div class="tool-tags">${tool.tags.map((tag) => `<span>${tag}</span>`).join("")}</div>
      </div>
      <button class="tool-action" type="button" data-tool="${tool.title}">Select</button>
    </article>
  `).join("");
  $$(".tool-action").forEach((button) => button.addEventListener("click", () => selectTool(button.dataset.tool)));
}

function resultRow(item, index, top = false) {
  return `<article class="result-row ${top ? "top" : ""}"><span class="rank">${index}</span><div><h3>${item.title}</h3><p>${item.reason}</p></div><div class="result-meta"><span>Cost: ${item.cost}</span><strong>${item.confidence}</strong></div></article>`;
}

function renderResults(selectedTool = null) {
  const list = $("#result-list");
  if (!list) return;
  const rows = [
    selectedTool ? { title: `${selectedTool} selected`, reason: "Next step is wiring this section to real account fields and scoring logic.", cost: "dev", confidence: "Starter" } : { title: "Build the Global Upgrade Plan first", reason: "Your account has many linked systems, so global ranking prevents wasted resources.", cost: "0", confidence: "High" },
    { title: "Protect gems until event value is known", reason: "Only spend when rewards clearly beat saving value.", cost: "Save", confidence: "High" },
    { title: "Rank gear, pet, and tech together", reason: "A pet or tech breakpoint can beat an equipment upgrade, so compare all three.", cost: "Compare", confidence: "Medium" }
  ];
  list.innerHTML = rows.map((item, index) => resultRow(item, index + 1, index === 0)).join("");
}

function selectTool(name) {
  renderResults(name);
  $("#planner")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateSnapshot() {
  const setText = (id, value) => { const el = $(id); if (el) el.textContent = value; };
  setText("#snap-chapter", $("#chapter")?.value || "—");
  setText("#snap-gems", Number($("#gems")?.value || 0).toLocaleString("en-US"));
  setText("#snap-survivor", ($("#survivor")?.value || "Yang").replace("Master ", ""));
  setText("#snap-mode", $("#mode")?.value || "Steamroll");
  setText("#snap-pet", $("#pet")?.value || "Eagle");
  setText("#snap-cores", $("#cores")?.value || "0");
}

function fillSample() {
  const values = { chapter: 126, gems: 51000, survivor: "Master Yang", weapon: "SS Starforged Havoc", pet: "Eagle", cores: 2, mode: "Steamroll", goal: "Max DPS" };
  Object.entries(values).forEach(([id, value]) => { const el = $("#" + id); if (el) el.value = value; });
  updateSnapshot();
  renderResults();
}

$("#tool-search")?.addEventListener("input", renderTools);
$("#generate-plan")?.addEventListener("click", () => { updateSnapshot(); renderResults(); $("#results")?.scrollIntoView({ behavior: "smooth", block: "start" }); });
$("#sample-btn")?.addEventListener("click", fillSample);
$$("#planner-form input, #planner-form select").forEach((input) => input.addEventListener("input", updateSnapshot));

renderCategories();
renderTools();
renderResults();
updateSnapshot();
