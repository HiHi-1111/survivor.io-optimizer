(() => {
  const CDN = "https://wsrv.nl/?url=https://sio-cdn.exp0.dev/icons/";
  const COLLECTIBLES = [{"name":"Dreamscape Puzzle","rarity":"Legend","stars":5,"path":"collectibles/dreamscape_puzzle.webp"},{"name":"Omni-Symbiote","rarity":"Legend","stars":5,"path":"collectibles/omni_symbiote.webp"},{"name":"Spatial Rewinder","rarity":"Legend","stars":5,"path":"collectibles/spatial_rewinder.webp"},{"name":"Temporal Rewinder","rarity":"Legend","stars":5,"path":"collectibles/temporal_rewinder.webp"},{"name":"Timeline Cube","rarity":"Legend","stars":5,"path":"collectibles/timeline_cube.webp"},{"name":"Aries Starlight","rarity":"Legend","stars":5,"path":"collectibles/aries_starlight.webp"},{"name":"Time Essence Bottle","rarity":"Legend","stars":5,"path":"collectibles/time_essence_bottle.webp"},{"name":"Human Genome Mapping","rarity":"Legend","stars":5,"path":"collectibles/human_genome_mapping.webp"},{"name":"Angelic Tear Crystal","rarity":"Legend","stars":5,"path":"collectibles/angelic_tear_crystal.webp"},{"name":"Otherworld Key","rarity":"Legend","stars":5,"path":"collectibles/otherworld_key.webp"},{"name":"Immortal Lucky Coin","rarity":"Legend","stars":5,"path":"collectibles/immortal_lucky_coin.webp"},{"name":"Book of Ancient Wisdom","rarity":"Legend","stars":5,"path":"collectibles/book_of_ancient_wisdom.webp"},{"name":"Dragon Tooth","rarity":"Legend","stars":5,"path":"collectibles/dragon_tooth.webp"},{"name":"Instellar Transition Matrix Design","rarity":"Legend","stars":5,"path":"collectibles/instellar_transition_matrix_design.webp"},{"name":"High-Lat Energy Cube","rarity":"Legend","stars":5,"path":"collectibles/high_lat_energy_cube.webp"},{"name":"Void Bloom","rarity":"Legend","stars":5,"path":"collectibles/void_bloom.webp"},{"name":"Unicorn's Horn","rarity":"Legend","stars":5,"path":"collectibles/unicorn_s_horn.webp"},{"name":"Eye of True Vision","rarity":"Legend","stars":5,"path":"collectibles/eye_of_true_vision.webp"},{"name":"Life Hourglass","rarity":"Legend","stars":5,"path":"collectibles/life_hourglass.webp"},{"name":"Nano-Mimetic Mask","rarity":"Legend","stars":5,"path":"collectibles/nano_mimetic_mask.webp"},{"name":"Starcore Diamond","rarity":"Legend","stars":5,"path":"collectibles/starcore_diamond.webp"},{"name":"Dice of Destiny","rarity":"Legend","stars":5,"path":"collectibles/dice_of_destiny.webp"},{"name":"Dimension Foil","rarity":"Legend","stars":5,"path":"collectibles/dimension_foil.webp"},{"name":"Mental Sync Helm","rarity":"Legend","stars":5,"path":"collectibles/mental_sync_helm.webp"},{"name":"Hyper Neuron","rarity":"Legend","stars":5,"path":"collectibles/hyper_neuron.webp"},{"name":"Cyber Totem","rarity":"Legend","stars":5,"path":"collectibles/cyber_totem.webp"},{"name":"Clone Mirror","rarity":"Legend","stars":5,"path":"collectibles/clone_mirror.webp"},{"name":"Aquarius Starlight","rarity":"Legend","stars":5,"path":"collectibles/aquarius_starlight.webp"},{"name":"Atomic Mech","rarity":"Legend","stars":5,"path":"collectibles/atomic_mech.webp"},{"name":"Gene Splicer","rarity":"Legend","stars":5,"path":"collectibles/gene_splicer.webp"},{"name":"Memory Editor","rarity":"Legend","stars":5,"path":"collectibles/memory_editor.webp"},{"name":"Holodream Fluid","rarity":"Legend","stars":5,"path":"collectibles/holodream_fluid.webp"},{"name":"Dark Matter Construct","rarity":"Legend","stars":5,"path":"collectibles/dark_matter_construct.webp"},{"name":"Prophet's Tarot","rarity":"Legend","stars":5,"path":"collectibles/prophet_s_tarot.webp"},{"name":"Pisces Starlight","rarity":"Legend","stars":5,"path":"collectibles/pisces_starlight.webp"},{"name":"Taurus Starlight","rarity":"Legend","stars":5,"path":"collectibles/taurus_starlight.webp"},{"name":"Golden Cutlery","rarity":"Epic","stars":4,"path":"collectibles/golden_cutlery.webp"},{"name":"Old Medical Book","rarity":"Epic","stars":4,"path":"collectibles/old_medical_book.webp"},{"name":"Savior's Memento","rarity":"Epic","stars":4,"path":"collectibles/savior_s_memento.webp"},{"name":"Safehouse Map","rarity":"Epic","stars":4,"path":"collectibles/safehouse_map.webp"},{"name":"Lucky Charm","rarity":"Epic","stars":4,"path":"collectibles/lucky_charm.webp"},{"name":"Scientific Luminary's Journal","rarity":"Epic","stars":4,"path":"collectibles/scientific_luminary_s_journal.webp"},{"name":"Super Circuit Board","rarity":"Epic","stars":4,"path":"collectibles/super_circuit_board.webp"},{"name":"Mystical Halo","rarity":"Epic","stars":4,"path":"collectibles/mystical_halo.webp"},{"name":"Tablet of Epics","rarity":"Epic","stars":4,"path":"collectibles/tablet_of_epics.webp"},{"name":"Primordial War Drum","rarity":"Epic","stars":4,"path":"collectibles/primordial_war_drum.webp"},{"name":"Flaming Plume","rarity":"Epic","stars":4,"path":"collectibles/flaming_plume.webp"},{"name":"Astral Dewdrop","rarity":"Epic","stars":4,"path":"collectibles/astral_dewdrop.webp"},{"name":"Nuclear Battery","rarity":"Epic","stars":4,"path":"collectibles/nuclear_battery.webp"},{"name":"Plasma Sword","rarity":"Epic","stars":4,"path":"collectibles/plasma_sword.webp"},{"name":"Golden Horn","rarity":"Epic","stars":4,"path":"collectibles/golden_horn.webp"},{"name":"Elemental Ring","rarity":"Epic","stars":4,"path":"collectibles/elemental_ring.webp"},{"name":"Anti-Gravity Device","rarity":"Epic","stars":4,"path":"collectibles/anti_gravity_device.webp"},{"name":"Hydraulic Flipper","rarity":"Epic","stars":4,"path":"collectibles/hydraulic_flipper.webp"},{"name":"Superhuman Pill","rarity":"Epic","stars":4,"path":"collectibles/superhuman_pill.webp"},{"name":"Comms Conch","rarity":"Epic","stars":4,"path":"collectibles/comms_conch.webp"},{"name":"Mini Dyson Sphere","rarity":"Epic","stars":4,"path":"collectibles/mini_dyson_sphere.webp"},{"name":"Micro Artificial Sun","rarity":"Epic","stars":4,"path":"collectibles/micro_artificial_sun.webp"},{"name":"Klein Bottle","rarity":"Epic","stars":4,"path":"collectibles/klein_bottle.webp"},{"name":"Antiparticle Gourd","rarity":"Epic","stars":4,"path":"collectibles/antiparticle_gourd.webp"},{"name":"Wildfire Furnace","rarity":"Epic","stars":4,"path":"collectibles/wildfire_furnace.webp"},{"name":"Infinity Score","rarity":"Epic","stars":4,"path":"collectibles/infinity_score.webp"},{"name":"Cosmic Compass","rarity":"Epic","stars":4,"path":"collectibles/cosmic_compass.webp"},{"name":"Wormhole Detector","rarity":"Epic","stars":4,"path":"collectibles/wormhole_detector.webp"},{"name":"Shuttle Capsule","rarity":"Epic","stars":4,"path":"collectibles/shuttle_capsule.webp"},{"name":"Neurochip","rarity":"Epic","stars":4,"path":"collectibles/neurochip.webp"},{"name":"Star-Rail Passenger Card","rarity":"Epic","stars":4,"path":"collectibles/star_rail_passenger_card.webp"},{"name":"Portable Mech Case","rarity":"Epic","stars":4,"path":"collectibles/portable_mech_case.webp"},{"name":"Geocore Orb","rarity":"Epic","stars":4,"path":"collectibles/geocore_orb.webp"},{"name":"Aquacore Orb","rarity":"Epic","stars":4,"path":"collectibles/aquacore_orb.webp"},{"name":"Pyrocore Orb","rarity":"Epic","stars":4,"path":"collectibles/pyrocore_orb.webp"},{"name":"Aerocore Orb","rarity":"Epic","stars":4,"path":"collectibles/aerocore_orb.webp"},{"name":"Gemini Starlight","rarity":"Epic","stars":4,"path":"collectibles/gemini_starlight.webp"},{"name":"Cancer Starlight","rarity":"Epic","stars":4,"path":"collectibles/cancer_starlight.webp"},{"name":"Leo Starlight","rarity":"Epic","stars":4,"path":"collectibles/leo_starlight.webp"},{"name":"Virgo Starlight","rarity":"Epic","stars":4,"path":"collectibles/virgo_starlight.webp"}];

  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
  const slug = value => String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  const selectedKey = name => `collectible:${slug(name)}`;

  function stars(count, max = 5) {
    return `<span class="stars">${Array.from({length:max}, (_, i) => `<span class="${i < count ? "star-on" : "star-off"}">★</span>`).join("")}</span>`;
  }

  function selectedFromStorage(name) {
    for (const key of ["survivorOptimizerProfileV10","survivorOptimizerProfileV9","survivorOptimizerProfileV8"]) {
      try {
        const data = JSON.parse(localStorage.getItem(key) || "null");
        if (data?.selected?.[selectedKey(name)] || data?.sel?.[selectedKey(name)]) return true;
      } catch {}
    }
    return false;
  }

  function renderCollectibles() {
    const host = $("#collectibles-grid");
    if (!host) return;
    const filter = ($(".filter-input")?.value || "").toLowerCase();
    const hideEvent = ($(".hide-row input")?.checked);
    let rows = COLLECTIBLES.map((item, idx) => ({...item, idx, set:`${item.rarity} Set ${Math.floor(idx/10)+1}`}))
      .filter(item => (!hideEvent || !item.name.startsWith("Event ")) && (!filter || (item.name + " " + item.rarity + " " + item.set).toLowerCase().includes(filter)));

    const orderOn = document.body.dataset.collectibleOrder === "stars";
    const setOn = document.body.dataset.collectibleSet === "true";
    if (orderOn) rows.sort((a,b) => b.stars - a.stars || a.name.localeCompare(b.name));
    if (setOn) rows.sort((a,b) => a.set.localeCompare(b.set) || a.name.localeCompare(b.name));

    host.innerHTML = rows.map(item => `<article class="collectible-card clickable-card ${selectedFromStorage(item.name) ? "is-selected" : ""}" data-card="collectible" data-name="${esc(item.name)}">` +
      `<span class="corner-badge">${esc(item.rarity[0])}</span>` +
      `<div class="collectible-icon icon-block has-asset"><img class="asset-real" src="${CDN + item.path}" alt="${esc(item.name)}" loading="lazy"><span class="art-mark">${esc(item.name.slice(0,3).toUpperCase())}</span></div>` +
      `<div class="card-label">${esc(item.name)}</div>${stars(item.stars, 5)}</article>`).join("");
  }

  document.addEventListener("click", ev => {
    const tab = ev.target.closest(".tab-btn");
    if (tab) {
      const text = tab.textContent.trim();
      if (text === "Order") document.body.dataset.collectibleOrder = document.body.dataset.collectibleOrder === "stars" ? "default" : "stars";
      if (text === "Sets") document.body.dataset.collectibleSet = document.body.dataset.collectibleSet === "true" ? "false" : "true";
      setTimeout(renderCollectibles, 0);
    }
    if (ev.target.closest("[data-card='collectible']")) setTimeout(renderCollectibles, 0);
  });

  document.addEventListener("input", ev => {
    if (ev.target.matches(".filter-input")) renderCollectibles();
  });

  document.addEventListener("change", ev => {
    if (ev.target.matches(".hide-row input")) renderCollectibles();
  });

  const start = () => { renderCollectibles(); setTimeout(renderCollectibles, 50); setTimeout(renderCollectibles, 300); };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
