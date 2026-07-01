(() => {
  const running = new Set();
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const actionLabels = new Map();

  function toast(text) {
    document.querySelector(".guard-note")?.remove();
    const el = document.createElement("div");
    el.className = "guard-note";
    el.textContent = text;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2200);
  }

  function selectedCount(selector) {
    return $$(selector).filter(x => x.classList.contains("is-selected")).length;
  }

  function estimateCombos() {
    const gear = selectedCount(".gear-card");
    const tech = selectedCount(".tech-top-card");
    const skills = selectedCount(".skill-card");
    const pets = selectedCount(".pet-card");
    const mounts = selectedCount(".mount-card");
    const raw = Math.max(1, (gear || 1) * Math.max(1, tech || 1) * Math.max(1, skills || 1) * Math.max(1, pets || 1) * Math.max(1, mounts || 1));
    return { gear, tech, skills, pets, mounts, total: raw };
  }

  function setBusy(btn, busy, text) {
    if (!btn) return;
    if (!actionLabels.has(btn)) actionLabels.set(btn, btn.textContent.trim() || "Run");
    btn.disabled = busy;
    btn.classList.toggle("btn-loading", busy);
    btn.classList.toggle("is-running", busy);
    if (busy) {
      btn.textContent = text || "Working...";
      let bar = document.createElement("span");
      bar.className = "btn-progress";
      btn.appendChild(bar);
    } else {
      btn.textContent = actionLabels.get(btn);
    }
  }

  function setProgress(btn, pct) {
    const bar = btn?.querySelector?.(".btn-progress");
    if (bar) bar.style.width = Math.max(0, Math.min(100, pct)) + "%";
  }

  function runWorker(btn, payload) {
    return new Promise((resolve, reject) => {
      let worker;
      try {
        worker = new Worker("opt-worker.js?v=1");
      } catch (err) {
        reject(err);
        return;
      }
      const timer = setTimeout(() => {
        worker.terminate();
        reject(new Error("Timed out"));
      }, 8000);
      worker.onmessage = event => {
        const msg = event.data || {};
        if (msg.type === "PROGRESS") setProgress(btn, msg.pct || 0);
        if (msg.type === "DONE") {
          clearTimeout(timer);
          worker.terminate();
          resolve(msg);
        }
      };
      worker.onerror = err => {
        clearTimeout(timer);
        worker.terminate();
        reject(err);
      };
      worker.postMessage({ type: "RUN", ...payload });
    });
  }

  async function handleOptimize(btn) {
    const key = btn.id || btn.textContent.trim() || "button";
    if (running.has(key)) return;
    const combo = estimateCombos();
    if (combo.skills > 6) {
      toast("Too many active skills. Deselect skills until you are at 6 or fewer.");
      return;
    }
    if (combo.total > 50000) {
      toast("Too many combinations. Narrow gear, tech, pets, or mounts first.");
      return;
    }
    running.add(key);
    setBusy(btn, true, "Crunching builds...");
    try {
      const result = await runWorker(btn, { count: Math.max(1000, combo.total * 60), selected: combo.gear + combo.tech + combo.skills + combo.pets + combo.mounts });
      btn.classList.add("btn-success");
      toast(`Optimization complete: checked ${Number(result.checked || 0).toLocaleString()} combinations.`);
      setTimeout(() => btn.classList.remove("btn-success"), 1400);
    } catch (err) {
      btn.classList.add("btn-error");
      toast("Optimization stopped safely. Narrow inputs and try again.");
      setTimeout(() => btn.classList.remove("btn-error"), 1600);
    } finally {
      running.delete(key);
      setBusy(btn, false);
    }
  }

  function wire() {
    const optimize = $("#optimize-items");
    if (optimize && !optimize.dataset.polished) {
      optimize.dataset.polished = "true";
      optimize.addEventListener("click", ev => {
        ev.preventDefault();
        ev.stopImmediatePropagation();
        handleOptimize(optimize);
      }, true);
    }

    ["#export-profile", "#share-profile", "#reset-profile"].forEach(sel => {
      const btn = $(sel);
      if (!btn || btn.dataset.polished) return;
      btn.dataset.polished = "true";
      btn.addEventListener("click", () => {
        btn.classList.add("btn-success");
        setTimeout(() => btn.classList.remove("btn-success"), 900);
      }, true);
    });
  }

  document.addEventListener("click", ev => {
    const chip = ev.target.closest(".support-chip,.tab-btn,.inline-edit-btn,.mini-btn,button[data-sys],button[data-scenario]");
    if (!chip || chip.disabled) return;
    chip.animate([{ transform: "scale(.985)" }, { transform: "scale(1)" }], { duration: 130, easing: "ease-out" });
  }, true);

  const start = () => { wire(); setTimeout(wire, 200); setTimeout(wire, 800); };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
