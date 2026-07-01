(() => {
  const MAX_SKILLS = 6;
  const MAX_TECH = 20;
  const STORE_KEYS = ["survivorOptimizerProfileV10", "survivorOptimizerProfileV9", "survivorOptimizerProfileV8"];
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  function note(text) {
    document.querySelector(".guard-note")?.remove();
    const div = document.createElement("div");
    div.className = "guard-note";
    div.textContent = text;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 2200);
  }

  function cleanNumberInput(input) {
    if (!input) return;
    input.removeAttribute("min");
    input.removeAttribute("max");
    input.inputMode = "numeric";
    input.addEventListener("input", () => {
      const old = input.value;
      const next = old.replace(/[^0-9]/g, "");
      if (old !== next) input.value = next;
    });
  }

  function selectedCards(selector) {
    return $$(selector).filter(x => x.classList.contains("is-selected"));
  }

  document.addEventListener("click", ev => {
    const skill = ev.target.closest(".skill-card[data-card='skill']");
    if (skill && !skill.classList.contains("is-selected") && selectedCards(".skill-card[data-card='skill']").length >= MAX_SKILLS) {
      ev.preventDefault();
      ev.stopImmediatePropagation();
      note("Max active skills reached. Deselect one first.");
      return;
    }
    const tech = ev.target.closest(".tech-top-card[data-card='tech']");
    if (tech && !tech.classList.contains("is-selected") && selectedCards(".tech-top-card[data-card='tech']").length >= MAX_TECH) {
      ev.preventDefault();
      ev.stopImmediatePropagation();
      note("Too many tech parts selected. Narrow the setup first.");
    }
  }, true);

  function compact(n) {
    if (!Number.isFinite(n)) return "";
    const units = ["", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc"];
    let i = 0;
    while (Math.abs(n) >= 1000 && i < units.length - 1) { n /= 1000; i++; }
    return (n >= 100 ? n.toFixed(0) : n >= 10 ? n.toFixed(1) : n.toFixed(2)).replace(/\.0+$|0+$/g, "") + units[i];
  }

  function formatDamage() {
    const el = $("#total-damage");
    if (!el) return;
    const raw = Number(String(el.textContent).replace(/[^0-9]/g, ""));
    if (raw > 999999999999) {
      el.title = raw.toLocaleString("en-US");
      el.textContent = compact(raw);
    }
  }

  function fixInputs() {
    ["#base-atk", "#total-atk", "#final-atk", "#designs", "#clan-level"].forEach(s => cleanNumberInput($(s)));
  }

  function addStatus() {
    if ($(".calc-warning")) return;
    const atk = $("#atk") || $(".left-stack");
    if (!atk) return;
    const div = document.createElement("div");
    div.className = "calc-warning";
    div.textContent = "Non-equipment ATK still needs your in-game Detailed Stats. This guard prevents bad inputs and illegal over-selection.";
    atk.prepend(div);
  }

  const start = () => {
    fixInputs();
    addStatus();
    formatDamage();
    const damage = $("#total-damage");
    if (damage) new MutationObserver(formatDamage).observe(damage, {childList:true, characterData:true, subtree:true});
  };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
