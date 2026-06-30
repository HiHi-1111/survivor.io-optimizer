(() => {
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "readability-fix.css?v=7";
  document.head.appendChild(css);

  const files = ["asset-paths.js?v=1", "app-data.js?v=7", "app-render.js?v=6", "app-actions.js?v=6"];
  const load = (i = 0) => {
    if (i >= files.length) return;
    const script = document.createElement("script");
    script.src = files[i];
    script.async = false;
    script.onload = () => load(i + 1);
    script.onerror = () => {
      console.warn("Optional app file failed to load", files[i]);
      load(i + 1);
    };
    document.body.appendChild(script);
  };
  load();
})();
