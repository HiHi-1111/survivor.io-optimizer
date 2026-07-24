# Survivor.io Optimizer

A source-traced, DPS-focused Survivor.io optimizer with structured knowledge,
profile-gated actions, and optional CUDA batch ranking.

Start with [docs/PROJECT_MAP.md](docs/PROJECT_MAP.md) for the complete folder
map and common workflows.

## DTlgrind one-click browser runner

On Windows, double-click:

```text
start_dtlgrind_optimizer.bat
```

The launcher opens `http://127.0.0.1:8765/` in the default browser. Press
**Start Optimization** to run the saved `profiles/dtlgrind.json` account.
The page reports live elapsed time, exact profiles checked, profiles remaining,
scoring speed, ETA, the highest damage found, and the corresponding resource
spend/refund action.

The job writes a resumable audit checkpoint after every scoring batch to:

```text
training_outputs/browser_jobs/dtlgrind_latest.json
```

The browser counters are derived from the actual generated transition set and
completed exact sIO scoring batches. A result is marked `complete` only when all
mapped configuration searches report complete. If an exact frontier exceeds its
state budget, the page marks the run `incomplete` instead of presenting a
provisional result as globally proven.

Command-line launch:

```powershell
python -m app.browser_runner
```

Useful options:

```powershell
python -m app.browser_runner --no-browser --port 8765 --chunk-size 128
```

## Main entrypoints

- Browser runner: `python -m app.browser_runner`
- Application demo: `python -m app.cli`
- Compatibility demo: `python run_demo.py`
- Optimizer API: `optimizer.main.optimize(player_state)`
- Source-pack extraction: `python tools/extract_source_pack.py`
- Source-pack validation: `python tools/validate_source_pack.py`
- Trainer: `tools/run_training.ps1`
- Trainer readiness: `python tools/check_trainer_ready.py --device cuda`
- Learning diagnostics: `python tools/inspect_learning.py`

## Important data

- DTlgrind account profile: `profiles/dtlgrind.json`
- Master source map: `data_sources/source_pack/source_database_map.pdf`
- Raw source pack: `data_sources/source_pack/raw/`
- Normalized database: `knowledge/source_pack/`
- Schemas: `knowledge/schemas/`
- Review queue: `knowledge/review_queue/`
- GPU numeric tables: `knowledge/gpu_tables/`
- Latest training summaries: `training_outputs/latest_*.json`
- Stable final metrics: `training_outputs/latest_final_summary.json`
- User-facing reports: `reports/`

## Quick validation

```powershell
.\.venv\Scripts\python.exe tools\validate_source_pack.py
.\.venv\Scripts\python.exe -m pytest tests\test_project_layout.py tests\test_training_startup.py tests\test_browser_runner.py -q
```

The root `run_demo.py` remains as a compatibility wrapper. New application
code belongs under `app/`; optimizer logic remains under `optimizer/`.
