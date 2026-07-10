# sIO Tools training pipeline

This folder is for training the Survivor.io optimizer from the uploaded `sio_tools.exp0.dev.zip` static site export.

The goal is not to copy the site UI. The goal is to learn the same data shape and evaluation flow:

1. Extract bundled game data and formula locations from the Next.js / webpack chunks.
2. Normalize those into optimizer tables: gear AF E/V/C, tech resonance, xeno pet awakening, pet skills, collectibles, and choice-item outputs.
3. Generate every legal spend allocation from the player's current inventory.
4. Simulate the full after-build for each allocation.
5. Score damage from the extracted stat model.
6. Output a plain list: `SOURCE ITEM xN -> PICK Y -> END ITEM Z -> FINAL BUILD`.

Important DTlgrind rules:

- The 45 relic cores are already inside the current build. They are not free/spendable currency.
- Only 23 awakening cores are movable, because they can be pulled from other Xeno pet awakening stars.
- The optimizer must compare all choices together. It must not pre-split into Gear / Tech / Pet lanes and it must not force relic cores.

Run extraction locally:

```bash
python tools/sio_training/extract_sio_bundle.py /path/to/sio_tools.exp0.dev.zip --out data/sio_training/generated
```

The generated corpus tells us which chunks/modules contain the formulas and data. The next step is normalizing module 37013 into machine-readable tables.