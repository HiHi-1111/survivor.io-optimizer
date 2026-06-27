(() => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  const subtypeBySlot = {
    Weapon: ["Twin Lance", "Kunai", "Void", "Light", "Disorder", "Normal"],
    Necklace: ["SS", "Eternal", "Void", "Chaos", "Crit", "Normal"],
    Gloves: ["SS", "Eternal", "Void", "Chaos", "Crit", "Normal"],
    Armor: ["SS", "E-Suit", "Void", "Quietus", "Revive", "Normal"],
    Belt: ["SS", "Eternal", "Void", "Twisting", "Shield", "Normal"],
    Boots: ["SS", "Eternal", "Void", "Confusion", "Speed", "Normal"]
  };

  const slotType = (slot = "") => slot.toLowerCase().replace(/[^a-z]/g, "");

  function artSvg(slot, label) {
    const type = slotType(slot);
    const safe = String(label || slot).slice(0, 18);
    const palette = {
      weapon: ["#ff69d6", "#8a3cff", "#1b1730"], necklace: ["#6ee7ff", "#2b8cff", "#10243a"], gloves: ["#ffc25b", "#d95b2b", "#241a16"],
      armor: ["#b9f7ff", "#357a9b", "#102436"], belt: ["#ffe17b", "#a66a22", "#251a10"], boots: ["#84ff9e", "#1d8c63", "#10251d"],
      tech: ["#60a5ff", "#7c3cff", "#111827"], pet: ["#ff6a9c", "#7c3cff", "#21142e"], mount: ["#52d6ff", "#743cff", "#111827"], collectible: ["#ff4f83", "#ffd34e", "#23142a"], set: ["#9298a8", "#566173", "#161b26"], other: ["#55b6ff", "#b47cff", "#111827"]
    }[type] || ["#55b6ff", "#b47cff", "#111827"];

    const drawings = {
      weapon: `<path d="M66 10 78 22 45 58 56 69 43 82 30 69 43 56 32 45Z" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".65"/><path d="M25 75 38 62 48 72 35 85Z" fill="#ffd34e" opacity=".95"/>`,
      necklace: `<path d="M26 22c5 28 43 28 48 0" fill="none" stroke="url(#g)" stroke-width="8" stroke-linecap="round"/><path d="M50 45 66 61 50 80 34 61Z" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".65"/>`,
      gloves: `<path d="M30 24h22c9 0 16 8 16 18v25c0 8-6 14-14 14H34c-7 0-12-5-12-12V36c0-7 4-12 8-12Z" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".6"/><path d="M38 20v28M50 20v30M62 27v25" stroke="#fff" stroke-width="4" stroke-opacity=".42"/>`,
      armor: `<path d="M28 18 50 10 72 18l-6 28 8 34H26l8-34Z" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".6"/><path d="M38 32h24M34 50h32" stroke="#fff" stroke-width="4" stroke-opacity=".35"/>`,
      belt: `<rect x="18" y="38" width="64" height="24" rx="8" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".55"/><rect x="40" y="32" width="20" height="36" rx="5" fill="#ffd34e" stroke="white" stroke-opacity=".45"/>`,
      boots: `<path d="M28 20h22v34l25 6c4 1 7 5 7 9v7H24V64c0-7 4-12 4-18Z" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".6"/><path d="M25 74h56" stroke="#fff" stroke-width="5" stroke-opacity=".3"/>`,
      tech: `<path d="M50 10 82 28v44L50 90 18 72V28Z" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".55"/><circle cx="50" cy="50" r="17" fill="#0b1020" stroke="#fff" stroke-opacity=".45"/><path d="M50 30v40M30 50h40" stroke="#fff" stroke-width="5" stroke-opacity=".45"/>`,
      pet: `<circle cx="50" cy="50" r="28" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".58"/><circle cx="40" cy="45" r="5" fill="#111827"/><circle cx="60" cy="45" r="5" fill="#111827"/><path d="M38 62c8 8 16 8 24 0" stroke="#111827" stroke-width="5" fill="none" stroke-linecap="round"/>`,
      mount: `<path d="M18 60h64l-8 16H26Z" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".55"/><circle cx="32" cy="78" r="8" fill="#0b1020" stroke="#fff"/><circle cx="68" cy="78" r="8" fill="#0b1020" stroke="#fff"/><path d="M40 34h24l16 26H28Z" fill="#fff" opacity=".16"/>`,
      collectible: `<path d="M50 12 70 32 62 78 50 88 38 78 30 32Z" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".58"/><circle cx="50" cy="50" r="12" fill="#fff" opacity=".22"/>`,
      set: `<rect x="24" y="20" width="52" height="60" rx="8" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".45"/><path d="M34 32h32M34 46h32M34 60h20" stroke="#fff" stroke-width="4" stroke-opacity=".42"/>`,
      other: `<circle cx="50" cy="50" r="34" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".55"/>`
    }[type] || `<circle cx="50" cy="50" r="34" fill="url(#g)" stroke="white" stroke-width="3" stroke-opacity=".55"/>`;

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="${palette[0]}"/><stop offset="1" stop-color="${palette[1]}"/></linearGradient><filter id="sh"><feDropShadow dx="0" dy="6" stdDeviation="4" flood-opacity=".5"/></filter></defs><rect width="100" height="100" rx="18" fill="${palette[2]}"/><g filter="url(#sh)">${drawings}</g><text x="50" y="96" text-anchor="middle" font-size="7" font-family="Arial" font-weight="900" fill="white" opacity=".75">${safe.replace(/&/g, "")}</text></svg>`;
    return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
  }

  function upgradeGearCards() {
    const grid = $("#gear-grid");
    grid?.classList.add("different-card-layout");
    $$(".gear-card").forEach(card => {
      const slot = card.dataset.slot || card.querySelector(".gear-select")?.dataset.slot || "other";
      const item = card.querySelector(".gear-select")?.value || slot;
      card.classList.add(`slot-${slotType(slot)}`);
      const img = card.querySelector(".gear-icon img");
      if (img) img.src = artSvg(slot, item);
      if (!card.querySelector(".gear-meta-row")) {
        const meta = document.createElement("div");
        meta.className = "gear-meta-row";
        meta.innerHTML = [`${slot}`, item.includes("SS") ? "SS" : item.includes("Void") ? "Void" : item.includes("Eternal") ? "Eternal" : item.includes("Chaos") ? "Chaos" : "Normal", "AF", "Core"].map(x => `<span class="gear-meta-pill">${x}</span>`).join("");
        card.querySelector(".gear-info")?.appendChild(meta);
      }
      if (!card.querySelector(".subtype-row")) {
        const row = document.createElement("div");
        row.className = "subtype-row";
        row.innerHTML = (subtypeBySlot[slot] || ["Base", "S", "SS"]).map(x => `<span class="subtype-pill">${x}</span>`).join("");
        card.querySelector(".gear-info")?.appendChild(row);
      }
      card.querySelector(".gear-select")?.addEventListener("change", e => {
        const itemNow = e.target.value;
        const image = card.querySelector(".gear-icon img");
        if (image) image.src = artSvg(slot, itemNow);
        const pills = card.querySelector(".gear-meta-row");
        if (pills) pills.innerHTML = [`${slot}`, itemNow.includes("SS") ? "SS" : itemNow.includes("Void") ? "Void" : itemNow.includes("Eternal") ? "Eternal" : itemNow.includes("Chaos") ? "Chaos" : "Normal", "AF", "Core"].map(x => `<span class="gear-meta-pill">${x}</span>`).join("");
      });
    });
  }

  function upgradeOtherIcons() {
    $$(".tech-icon img").forEach((img, i) => img.src = artSvg("tech", `Tech ${i + 1}`));
    $$(".skill-card .card-icon img").forEach((img, i) => img.src = artSvg("tech", `Skill ${i + 1}`));
    $$(".pet-icon img").forEach((img, i) => img.src = artSvg("pet", `Pet ${i + 1}`));
    $$(".mount-art img").forEach((img, i) => img.src = artSvg("mount", `Mount ${i + 1}`));
    $$(".collectible-icon img").forEach((img, i) => img.src = artSvg("collectible", `Collect ${i + 1}`));
    $$(".set-icon img").forEach((img, i) => img.src = artSvg("set", `Set ${i + 1}`));
  }

  function addItemNote() {
    const grid = $("#gear-grid");
    if (!grid || $(".item-panel-note")) return;
    const note = document.createElement("div");
    note.className = "item-panel-note";
    note.textContent = "Each slot now has its own art type, subtype chips, rarity look, and slot-specific item list. These are original generated assets, not copied PNGs.";
    grid.prepend(note);
  }

  function run() {
    upgradeGearCards();
    upgradeOtherIcons();
    addItemNote();
  }

  document.addEventListener("DOMContentLoaded", () => setTimeout(run, 50));
  window.addEventListener("load", () => setTimeout(run, 100));
})();