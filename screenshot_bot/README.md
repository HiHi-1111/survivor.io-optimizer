# Survivor.io Screenshot Bot

This bot reads static screenshots and exports optimizer-ready JSON. It does not need model training to start.

## First target
Equipment screenshots only.

It uses:
- OpenCV template matching for item icons
- lightweight OCR hooks for levels/text later
- deterministic screen regions first, because mobile game screens are mostly fixed layouts

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r screenshot_bot/requirements.txt
```

## Run

```powershell
python -m screenshot_bot.run screenshots/input/equipment.png --type equipment --debug
```

Output:

```text
screenshots/output/profile.json
screenshots/debug/equipment_debug.png
```

## Do we need training?

Not at first. Start with template matching. Training only becomes useful later if screenshots vary too much, icons are missing, or OCR keeps failing.

## Folders

```text
screenshot_bot/
  run.py
  screen_detector.py
  template_matcher.py
  extract_equipment.py
  export_profile.py
  ocr.py
knowledge/icons/equipment/
screenshots/input/
screenshots/output/
screenshots/debug/
```
