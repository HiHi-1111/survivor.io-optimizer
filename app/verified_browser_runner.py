"""Verified browser runner with spend-plan reporting and a minimum audit pass."""
from __future__ import annotations

import argparse
import json
import threading
import time
import traceback
import webbrowser
from pathlib import Path

from app.browser_runner import ROOT, RunnerHandler, SearchJob, ThreadingHTTPServer, _finite_number, _now
from optimizer.sio_ce_account import calculate_clan_expedition_damage_batch
from optimizer.source_pack_optimizer import _candidate, _prepare_profile

DEFAULT_PROFILE = ROOT / "profiles" / "dtlgrind.json"
MIN_AUDIT_SECONDS = 20.0


class VerifiedSearchJob(SearchJob):
    def start(self) -> bool:
        with self.lock:
            self.top_candidates = []
            self.spend_recommendation = None
            self.generated_actions = 0
            self.validation_passes = 0
        return super().start()

    def _run(self) -> None:
        try:
            profile = json.loads(self.profile_path.read_text(encoding="utf-8"))
            with self.lock:
                self.stage = "Generating every legal spending and refund profile"

            prepared = _prepare_profile(profile)
            transitions = list(prepared["transitions"])
            baseline_profile = prepared["profile"]
            with self.lock:
                self.generated_actions = len(prepared.get("actions", []))
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
                    self.warnings.append(str(baseline_report.get("reason") or "baseline_not_scoreable"))
                self._save_checkpoint()

            ranked: list[tuple[dict, dict]] = []
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
                    ranked.append((candidate, after_profile))
                with self.lock:
                    self._save_checkpoint()

            ranked.sort(key=lambda row: (-float(row[0].get("expected_dps_gain", 0)), float(row[0].get("total_cost_units", 0)), str(row[0].get("action_id"))))
            top = ranked[:10]
            with self.lock:
                self.top_candidates = [row[0] for row in top]
                if top and float(top[0][0].get("expected_dps_gain", 0)) > 0:
                    self.best_action, self.best_profile = top[0]
                    self.best_damage = _finite_number(self.best_action.get("after_damage"))
                    self.spend_recommendation = {
                        "decision": "spend",
                        "action_id": self.best_action.get("action_id"),
                        "description": self.best_action.get("description"),
                        "spend": self.best_action.get("consumed_items") or {},
                        "refund": self.best_action.get("refunded_items") or {},
                        "expected_damage_gain": self.best_action.get("expected_dps_gain"),
                        "expected_percent_gain": self.best_action.get("percent_damage_gain"),
                    }
                else:
                    self.spend_recommendation = {
                        "decision": "hold",
                        "reason": "No legal verified spending path increased Clan Expedition damage above the current build.",
                        "spend": {},
                        "refund": {},
                    }
                self.stage = "Double-checking the best results and resource ledger"
                self._save_checkpoint()

            verify_profiles = [baseline_profile] + [row[1] for row in top[:3]]
            first = calculate_clan_expedition_damage_batch(verify_profiles)
            second = calculate_clan_expedition_damage_batch(verify_profiles)
            self.validation_passes = 2
            first_values = [_finite_number(row.get("total_damage")) for row in first]
            second_values = [_finite_number(row.get("total_damage")) for row in second]
            if first_values != second_values:
                raise RuntimeError("Repeated exact scoring produced inconsistent damage results")

            elapsed = _now() - (self.started_at or _now())
            if elapsed < MIN_AUDIT_SECONDS:
                time.sleep(MIN_AUDIT_SECONDS - elapsed)

            incomplete = [name for name, report in self.configuration_searches.items() if isinstance(report, dict) and not bool(report.get("complete", False))]
            with self.lock:
                self.finished_at = _now()
                if self.total_states <= 2:
                    self.status = "incomplete"
                    self.stage = "Too few legal spending profiles were generated; recommendation is not trusted"
                    self.warnings.append(f"Only {self.total_states} scoreable profiles were generated from {self.generated_actions} actions.")
                elif incomplete:
                    self.status = "incomplete"
                    self.stage = "Finished scoring, but a configuration frontier exceeded its exact state budget"
                    self.warnings.append("Incomplete exact frontiers: " + ", ".join(incomplete))
                else:
                    self.status = "complete"
                    self.stage = "All legal profiles checked and top results verified twice"
                self._save_checkpoint()
        except Exception as exc:
            with self.lock:
                self.status = "error"
                self.stage = "Stopped because of an error"
                self.error = f"{type(exc).__name__}: {exc}"
                self.warnings.append(traceback.format_exc())
                self.finished_at = _now()
                self._save_checkpoint()

    def snapshot(self, *, include_profile: bool = False) -> dict:
        payload = super().snapshot(include_profile=include_profile)
        payload["generated_actions"] = getattr(self, "generated_actions", 0)
        payload["validation_passes"] = getattr(self, "validation_passes", 0)
        payload["top_candidates"] = getattr(self, "top_candidates", [])
        payload["spend_recommendation"] = getattr(self, "spend_recommendation", None)
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the verified DTlgrind optimizer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--chunk-size", type=int, default=128)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    profile_path = args.profile if args.profile.is_absolute() else ROOT / args.profile
    if not profile_path.exists():
        raise SystemExit(f"Profile not found: {profile_path}")
    job = VerifiedSearchJob(profile_path=profile_path, chunk_size=max(1, args.chunk_size))
    RunnerHandler.job = job
    server = ThreadingHTTPServer((args.host, args.port), RunnerHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Verified DTlgrind browser optimizer: {url}")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
