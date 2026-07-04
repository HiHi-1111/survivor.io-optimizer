# Survivor.io Screenshot Bot

This bot reads static screenshots and exports optimizer-ready JSON. It does not need model training to start.

## Current targets

1. Equipment screen
2. My Bag / inventory screen with stack quantities
3. Detailed Stats screens: Survivor Stats, Pet Stats, Core Stock

It uses:
- OpenCV template matching for item icons
- grid detection to find item cells
- cropped OCR for stack quantities only
- cropped OCR for Detailed Stats rows
- debug images so you can see every box it detected

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r screenshot_bot/requirements.txt
```

## Run examples

Equipment:

```powershell
python -m screenshot_bot.run screenshots/input/equipment.png --type equipment --debug
```

Inventory / My Bag:

```powershell
python -m screenshot_bot.run screenshots/input/bag.png --type inventory --templates knowledge/icons/items --debug
```

Detailed Stats:

```powershell
python -m screenshot_bot.run screenshots/input/survivor_stats.png --type stats --debug
```

Output:

```text
screenshots/output/profile.json
screenshots/debug/*_debug.png
screenshots/debug/quantity_crops/
```

## How stackable items work

For every item cell:

```text
1. detect the colored grid cell
2. template match the icon inside that cell
3. crop the bottom-right quantity badge
4. OCR only that small crop
5. return item name, confidence, quantity, and box
```

This is much better than OCRing the whole screenshot.

## Do we need training?

No, not at first. Start with template matching and cropped OCR. Training only becomes useful later if screenshots vary too much, icons are missing, or OCR keeps failing.

## Folders

```text
screenshot_bot/
  run.py
  screen_detector.py
  grid_detector.py
  template_matcher.py
  extract_equipment.py
  extract_inventory.py
  extract_stats.py
  export_profile.py
  ocr.py
knowledge/icons/equipment/
knowledge/icons/items/
screenshots/input/
screenshots/output/
screenshots/debug/
```
