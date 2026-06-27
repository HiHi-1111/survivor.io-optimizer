(() => {
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "readability-fix.css?v=6";
  document.head.appendChild(css);

  const files = ["app-data.js?v=6", "app-render.js?v=6", "app-actions.js?v=6"];
  const load = (i = 0) => {
    if (i >= files.length) return;
    const script = document.createElement("script");
    script.src = files[i];
    script.async = false;
    script.onload = () => load(i + 1);
    script.onerror = () => console.error("Failed to load", files[i]);
    document.body.appendChild(script);
  };
  load();
})();
