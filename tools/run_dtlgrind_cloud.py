"""Run the DTlgrind optimizer in CI and build a static mobile report."""
from __future__ import annotations

import html
import json
import time
from pathlib import Path

from app.browser_runner import DEFAULT_PROFILE, SearchJob

ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "site"


def fmt_number(value):
    if value is None:
        return "—"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_duration(seconds):
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def render_report(result: dict) -> str:
    action = result.get("best_action") or {}
    warnings = result.get("warnings") or []
    status = str(result.get("status", "unknown"))
    rows = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in warnings
    ) or "<li>None</li>"
    action_json = html.escape(json.dumps(action, indent=2, default=str))
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>DTlgrind Optimizer Result</title>
<style>
body{{margin:0;background:#07111f;color:#eef6ff;font:16px system-ui,-apple-system,sans-serif}}main{{max-width:880px;margin:auto;padding:20px}}h1{{font-size:30px;margin-bottom:4px}}.muted{{color:#9cb0c7}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}}.card{{background:#102136;border:1px solid #24415f;border-radius:16px;padding:16px}}.big{{font-size:27px;font-weight:800}}.ok{{color:#53e3a6}}.warn{{color:#ffd166}}pre{{white-space:pre-wrap;word-break:break-word;background:#081725;border-radius:12px;padding:14px;overflow:auto}}a{{color:#72c8ff}}ul{{padding-left:20px}}
</style></head><body><main>
<h1>DTlgrind CE Optimizer</h1><div class=\"muted\">Latest cloud run result</div>
<div class=\"grid\">
<div class=\"card\"><div class=\"muted\">Status</div><div class=\"big {'ok' if status == 'complete' else 'warn'}\">{html.escape(status.upper())}</div></div>
<div class=\"card\"><div class=\"muted\">Highest damage</div><div class=\"big\">{fmt_number(result.get('best_damage'))}</div></div>
<div class=\"card\"><div class=\"muted\">Baseline</div><div class=\"big\">{fmt_number(result.get('baseline_damage'))}</div></div>
<div class=\"card\"><div class=\"muted\">Damage gain</div><div class=\"big\">{fmt_number(result.get('damage_gain'))}</div></div>
<div class=\"card\"><div class=\"muted\">Checked</div><div class=\"big\">{fmt_number(result.get('checked_states'))}</div></div>
<div class=\"card\"><div class=\"muted\">Discovered</div><div class=\"big\">{fmt_number(result.get('total_states'))}</div></div>
<div class=\"card\"><div class=\"muted\">Speed</div><div class=\"big\">{float(result.get('states_per_second') or 0):,.2f}/s</div></div>
<div class=\"card\"><div class=\"muted\">Elapsed</div><div class=\"big\">{fmt_duration(result.get('elapsed_seconds'))}</div></div>
</div>
<div class=\"card\"><h2>Stage</h2><p>{html.escape(str(result.get('stage') or ''))}</p></div>
<div class=\"card\"><h2>Best action</h2><pre>{action_json}</pre></div>
<div class=\"card\"><h2>Warnings / limits</h2><ul>{rows}</ul></div>
<p class=\"muted\">This page is regenerated after each cloud optimizer run. It reports actual scored states, not simulated progress.</p>
</main></body></html>"""


def main() -> None:
    job = SearchJob(profile_path=DEFAULT_PROFILE, chunk_size=128)
    if not job.start():
        raise SystemExit("Could not start search job")

    last_checked = -1
    while True:
        snapshot = job.snapshot()
        checked = int(snapshot.get("checked_states") or 0)
        if checked != last_checked:
            print(
                "status={status} checked={checked}/{total} rate={rate:.2f}/s "
                "elapsed={elapsed:.1f}s best={best}".format(
                    status=snapshot.get("status"),
                    checked=checked,
                    total=snapshot.get("total_states") or 0,
                    rate=float(snapshot.get("states_per_second") or 0),
                    elapsed=float(snapshot.get("elapsed_seconds") or 0),
                    best=snapshot.get("best_damage"),
                ),
                flush=True,
            )
            last_checked = checked
        if snapshot.get("status") in {"complete", "incomplete", "error"}:
            break
        time.sleep(5)

    result = job.snapshot(include_profile=True)
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (SITE_DIR / "index.html").write_text(render_report(result), encoding="utf-8")

    summary_path = Path(str(__import__("os").environ.get("GITHUB_STEP_SUMMARY", "")))
    if str(summary_path):
        summary_path.write_text(
            "# DTlgrind optimizer result\n\n"
            f"- Status: **{result.get('status')}**\n"
            f"- Highest damage: **{fmt_number(result.get('best_damage'))}**\n"
            f"- Baseline: **{fmt_number(result.get('baseline_damage'))}**\n"
            f"- Gain: **{fmt_number(result.get('damage_gain'))}**\n"
            f"- Checked: **{fmt_number(result.get('checked_states'))} / {fmt_number(result.get('total_states'))}**\n"
            f"- Elapsed: **{fmt_duration(result.get('elapsed_seconds'))}**\n",
            encoding="utf-8",
        )

    if result.get("status") == "error":
        raise SystemExit(result.get("error") or "optimizer failed")


if __name__ == "__main__":
    main()
