# PowerShell commands for Screenshot Bot

Run these from the repo root later on your laptop.

## 0) Open the repo folder

```powershell
Set-Location "C:\Users\iyoua\Downloads\survivor-optimizer"
```

If your folder is somewhere else, change the path.

## 1) One-command first setup

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\first_run_screenshot_bot.ps1
```

This creates `.venv`, installs requirements, and creates input/output/debug folders.

## 2) Manual setup version

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r screenshot_bot\requirements.txt
New-Item -ItemType Directory -Force screenshots\input
New-Item -ItemType Directory -Force screenshots\output
New-Item -ItemType Directory -Force screenshots\debug
New-Item -ItemType Directory -Force knowledge\icons\equipment
New-Item -ItemType Directory -Force knowledge\icons\items
```

## 3) Run a single My Bag / inventory screenshot

Put the image here:

```text
screenshots\input\bag.png
```

Run:

```powershell
python -m screenshot_bot.run screenshots\input\bag.png --type inventory --templates knowledge\icons\items --debug
```

Outputs:

```text
screenshots\output\profile.json
screenshots\debug\inventory_debug.png
screenshots\debug\quantity_crops\
```

## 4) Run a single Detailed Stats screenshot

```powershell
python -m screenshot_bot.run screenshots\input\survivor_stats.png --type stats --debug
```

Also use this for:

```text
pet_stats.png
core_stock.png
```

## 5) Run a single Equipment screenshot

```powershell
python -m screenshot_bot.run screenshots\input\equipment.png --type equipment --templates knowledge\icons\equipment --debug
```

## 6) Run all screenshots in the input folder

```powershell
python -m screenshot_bot.batch_run screenshots\input --type auto
```

If auto-detect is wrong, force one type:

```powershell
python -m screenshot_bot.batch_run screenshots\input --type inventory
python -m screenshot_bot.batch_run screenshots\input --type stats
python -m screenshot_bot.batch_run screenshots\input --type equipment
```

## 7) Check outputs

```powershell
Get-ChildItem screenshots\output
Get-ChildItem screenshots\debug
Get-Content screenshots\output\profile.json
Get-Content screenshots\output\batch_results.json
```

## 8) Open debug folder

```powershell
explorer screenshots\debug
```

Look for:

```text
inventory_debug.png       boxes around detected bag cells
stats_debug.png           boxes around stat rows
quantity_crops\           tiny OCR crops for item quantities
```

## 9) Common fixes

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

If Python is not found:

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If Tesseract is missing, the bot still runs but OCR text may be blank. Install Tesseract later, then rerun:

```powershell
winget install UB-Mannheim.TesseractOCR
```

Then close and reopen PowerShell.

## 10) What to send back to ChatGPT after first run

Send these files/screenshots:

```text
screenshots\debug\inventory_debug.png
screenshots\debug\stats_debug.png
screenshots\output\batch_results.json
```

The debug images show whether the boxes/crops are correct. The JSON shows whether OCR parsed the values correctly.
