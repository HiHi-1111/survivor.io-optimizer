onmessage = function (event) {
  const data = event.data || {};
  if (data.type !== "RUN") return;
  const n = Math.max(1, Math.min(30000, Number(data.count || 1000)));
  let score = 0;
  for (let i = 0; i < n; i++) {
    score = Math.max(score, (i % 997) + Number(data.selected || 0) * 10);
    if (i % 1000 === 0) postMessage({ type: "PROGRESS", pct: Math.round(i * 100 / n) });
  }
  postMessage({ type: "DONE", score: Math.round(score), checked: n });
};
