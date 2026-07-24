"""One-click local browser runner for exact Survivor.io CE optimization.

Run with: python -m app.browser_runner
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import traceback
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from optimizer.sio_ce_account import calculate_clan_expedition_damage_batch
from optimizer.source_pack_optimizer import _candidate, _prepare_profile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "profiles" / "dtlgrind.json"
WEB_ROOT = ROOT / "app" / "web"
CHECKPOINT_DIR = ROOT / "training_outputs" / "browser_jobs"


def _now() -> float:
    return time.time()


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


@dataclass
class SearchJob:
    profile_path: Path
    chunk_size: int = 128
    lock: threading.RLock = field(default_factory=threading.RLock)
    status: str = "idle"
    stage: str = "Ready"
    started_at: float | None = None
    finished_at: float | None = None
    total_states: int = 0
    checked_states: int = 0
    rejected_states: int = 0
    preflight_skipped: int = 0
    deduplicated_states: int = 0
    best_damage: float | None = None
    baseline_damage: float | None = None
    best_action: dict[str, Any] | None = None
    best_profile: dict[str, Any] | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    configuration_searches: dict[str, Any] = field(default_factory=dict)
    _thread: threading.Thread | None = None

    def start(self) -> bool:
        with self.lock:
            if self.status in {"preparing", "running"}:
                return False
            self.status = "preparing"
            self.stage = "Loading DTlgrind profile"
            self.started_at = _now()
            self.finished_at = None
            self.total_states = 0
            self.checked_states = 0
            self.rejected_states = 0
            self.preflight_skipped = 0
            self.deduplicated_states = 0
            self.best_damage = None
            self.baseline_damage = None
            self.best_action = None
            self.best_profile = None
            self.error = None
            self.warnings = []
            self.configuration_searches = {}
            self._thread = threading.Thread(target=self._run, name="dtlgrind-optimizer", daemon=True)
            self._thread.start()
            return True

    def _run(self) -> None:
        try:
            profile = json.loads(self.profile_path.read_text(encoding="utf-8"))
            with self.lock:
                self.stage = "Generating and deduplicating legal profiles"

            prepared = _prepare_profile(profile)
            transitions = list(prepared["transitions"])
            baseline_profile = prepared["profile"]
            with self.lock:
                self.rejected_states = len(prepared.get("rejected", []))
                self.preflight_skipped = len(prepared.get("preflight_skipped", []))
                self.deduplicated_states = len(prepared.get("deduplicated", []))
                self.configuration_searches = dict(prepared.get("configuration_searches") or {})
                self.total_states = 1 + len(transitions)
                self.status = "running"
                self.stage = "Scoring exact Clan Expedition damage"

            baseline_report = calculate_clan_expedition_damage_batch([baseline_profile])[0]
            baseline = _finite_number(baseline_report.get("total_damage"))
            with self.lock:
                self.checked_states = 1
                self.baseline_damage = baseline
                self.best_damage = baseline
                self.best_profile = baseline_profile
                if not baseline_report.get("supported"):
                    reason = baseline_report.get("reason") or "baseline_not_scoreable"
                    self.warnings.append(str(reason))
                self._save_checkpoint()

            for start in range(0, len(transitions), self.chunk_size):
                rows = transitions[start : start + self.chunk_size]
                reports = calculate_clan_expedition_damage_batch([row[1] for row in rows])
                for (action, after_profile, certificate), after_report in zip(rows, reports):
                    candidate, reason = _candidate(action, certificate, baseline_report, after_report)
                    with self.lock:
                        self.checked_states += 1
                        if candidate is None:
                            self.rejected_states += 1
                            if reason and len(self.warnings) < 25:
                                self.warnings.append(str(reason))
                            continue
                        damage = _finite_number(candidate.get("after_damage"))
                        if damage is not None and (self.best_damage is None or damage > self.best_damage):
                            self.best_damage = damage
                            self.best_action = candidate
                            self.best_profile = after_profile
                with self.lock:
                    self._save_checkpoint()

            incomplete = [
                name for name, report in self.configuration_searches.items()
                if isinstance(report, dict) and not bool(report.get("complete", False))
            ]
            with self.lock:
                self.finished_at = _now()
                if incomplete:
                    self.status = "incomplete"
                    self.stage = "Finished scoring, but a configuration frontier exceeded its exact state budget"
                    self.warnings.append("Incomplete exact frontiers: " + ", ".join(incomplete))
                else:
                    self.status = "complete"
                    self.stage = "All generated legal exact profiles checked"
                self._save_checkpoint()
        except Exception as exc:  # surfaced to browser with traceback retained in checkpoint
            with self.lock:
                self.status = "error"
                self.stage = "Stopped because of an error"
                self.error = f"{type(exc).__name__}: {exc}"
                self.warnings.append(traceback.format_exc())
                self.finished_at = _now()
                self._save_checkpoint()

    def _save_checkpoint(self) -> None:
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        payload = self.snapshot(include_profile=True)
        temporary = CHECKPOINT_DIR / "dtlgrind_latest.tmp"
        destination = CHECKPOINT_DIR / "dtlgrind_latest.json"
        temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        temporary.replace(destination)

    def snapshot(self, *, include_profile: bool = False) -> dict[str, Any]:
        with self.lock:
            now = self.finished_at or _now()
            elapsed = max(0.0, now - self.started_at) if self.started_at else 0.0
            rate = self.checked_states / elapsed if elapsed > 0 else 0.0
            remaining = max(0, self.total_states - self.checked_states)
            eta = remaining / rate if rate > 0 and self.status in {"preparing", "running"} else None
            gain = None
            gain_percent = None
            if self.best_damage is not None and self.baseline_damage is not None:
                gain = self.best_damage - self.baseline_damage
                if self.baseline_damage:
                    gain_percent = gain / self.baseline_damage * 100.0
            payload = {
                "profile": self.profile_path.stem,
                "status": self.status,
                "stage": self.stage,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "elapsed_seconds": elapsed,
                "total_states": self.total_states,
                "checked_states": self.checked_states,
                "remaining_states": remaining,
                "states_per_second": rate,
                "eta_seconds": eta,
                "rejected_states": self.rejected_states,
                "preflight_skipped": self.preflight_skipped,
                "deduplicated_states": self.deduplicated_states,
                "baseline_damage": self.baseline_damage,
                "best_damage": self.best_damage,
                "damage_gain": gain,
                "damage_gain_percent": gain_percent,
                "best_action": self.best_action,
                "error": self.error,
                "warnings": self.warnings[-25:],
                "configuration_searches": self.configuration_searches,
            }
            if include_profile:
                payload["best_profile"] = self.best_profile
            return payload


class RunnerHandler(BaseHTTPRequestHandler):
    job: SearchJob

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/status":
            self._json(self.job.snapshot())
            return
        if path == "/api/result":
            self._json(self.job.snapshot(include_profile=True))
            return
        if path in {"/", "/index.html"}:
            file_path = WEB_ROOT / "index.html"
            if not file_path.exists():
                self._json({"error": "app/web/index.html is missing"}, 500)
                return
            body = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/start":
            started = self.job.start()
            self._json({"started": started, **self.job.snapshot()}, 202 if started else 409)
            return
        self._json({"error": "not found"}, 404)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[browser-runner] {self.address_string()} - {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the DTlgrind optimizer in a local browser")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--chunk-size", type=int, default=128)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    profile_path = args.profile if args.profile.is_absolute() else ROOT / args.profile
    if not profile_path.exists():
        raise SystemExit(f"Profile not found: {profile_path}")
    job = SearchJob(profile_path=profile_path, chunk_size=max(1, args.chunk_size))
    RunnerHandler.job = job
    server = ThreadingHTTPServer((args.host, args.port), RunnerHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"DTlgrind browser optimizer: {url}")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping browser optimizer.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
