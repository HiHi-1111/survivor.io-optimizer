# Survivor.io Optimizer Final Scope and Source Boundaries

This document is the final source boundary for the Clan Expedition optimizer. It no longer represents a promise to invent or approximate missing game data. The supplied sIO bundle is the formula authority. Community guides, YouTube videos, descriptions, captions, screenshots, and transcripts may corroborate mechanics, but they cannot replace an exact source table unless the evidence is explicit, reproducible, and retained with provenance.

## Release blockers

None. The final branch passed the formula and uptime audit, combination and training-leakage audit, focused Python 3.11 and 3.12 suites, the complete Python 3.12 repository suite, inherited champion-lineage smoke tests, exact local tests with the source-locked sIO bundle, and Cloudflare preview deployment.

## Verified absent sIO worker chunks

The supplied ZIP registers the following workers in its service-worker manifest but does not contain their executable hashed chunks:

- `items`
- `tetris`
- `mountPuzzles`
- `resonance`
- `skills`
- `petsCores`
- `petsSkills`
- `collectiblesStars`
- `customSets`

These names are not hallucinated. Their expected chunk paths and hashes are preserved in `knowledge/sio_worker_manifest.json`, and their absence is checked against the source-locked bundle. The optimizer independently enumerates exact states where the available formulas and legal rules are sufficient, but it does not claim byte-for-byte parity with omitted worker search algorithms.

## Deliberately unsupported automatic actions

The following actions remain excluded because the supplied bundle does not publish enough exact legality, cost, return, or reset data. They are not guessed from community wording:

- Xeno Transmute effect-condition rerolls and reroll costs.
- Full Tech support-part reassignment, reserved-Legend, fodder, active-skill-count, and downgrade strategy parity.
- Overload levels beyond the last published resonance gate.
- Survivor reset, shard-conversion, level-resource, and refund tables not present in the bundle.
- Normal-pet rarity merge actions and assist-skill reassignment without a complete legal graph.
- Xeno awakening-power allocation, four-slot and empty-slot skill eligibility, Elixir swap costs, and dismiss or exchange losses.
- Universal collectible shard and edition costs, Custom Collection Set legality, and Legend Collectible Deconstructor returns.
- Mount fusion, refinement, reroll, reset, and refund costs.
- Puzzle-piece-to-component-stat values that are not supplied as verified aggregate stats.

A future source update may add these actions without changing the CE formula contract. Until then, the public optimizer reports them as unsupported instead of assigning invented values.

## Account and evidence inputs still accepted later

The implementation is final for the supplied source, but additional user evidence can improve coverage without changing hard mechanics:

- Authenticated sIO account exports can add field aliases and immutable real-account fixtures.
- Inventory screenshots can be parsed only with confidence values and manual correction for unclear fields.
- Repeated observed Clan Expedition runs can be stored for residual calibration and gap detection.
- Creator transcripts or screenshots can be retained as secondary evidence when they state a mechanic explicitly. Numeric values require a visible table, caption, or repeated independent verification before entering exact data.

Missing optional user evidence does not block this release.

## Current contract boundaries

- The optimizer supports Clan Expedition damage only.
- The public recommendation is selected exclusively by exact legal before-and-after CE damage.
- Learned models may order proposals but cannot replace the exact winner.
- Raw ownership changes must be scored from a `raw_profile` or another exact raw-account stage. A post-24804 stat snapshot is valid for damage calculation but is not treated as an ownership source for new upgrade simulations.
- Every generated action requires a complete state patch and a balanced consumption and refund ledger.
- An exact configuration search that exceeds its declared state budget withholds the global recommendation instead of presenting a partial winner.
- Choice chests use canonical multiset allocations and exact reward units. Pick order is never enumerated.
- Teamwork is an unordered combination. Main Survivor, Harmony left and right, Twinborn identity, and distinct Xeno support skill roles remain directional because changing those roles changes the resulting state.
- Mount placement geometry is deterministic solver output and never a learned feature. Only verified aggregate mount component stats may reach CE scoring or training labels.
- The source-locked oracle cache includes the oracle source hash, bundle hash, schema, and request, so code changes cannot reuse stale exact results.

## Work that should not be added

- Do not add Ender's Echo, chapters, Path of Trials, Lunar Mine Expedition, Zone Operation, Operation Retreat, or Survivor Showdown to this CE optimizer.
- Do not enumerate permutations of identical Tetris pieces, selector-chest picks, interchangeable Teamwork members, identical Xeno support roles, item sets, or any other order-independent choice.
- Do not train on Tetris coordinates, rotations, boards, paths, state counts, or solver internals.
- Do not convert vague YouTube commentary or community estimates into exact costs, gates, returns, damage values, or legal transitions.
- Do not claim parity with omitted sIO worker algorithms.
- Do not use rarity points, generic breakpoint scores, community preferences, or learned scores as the final winner.
- Do not delete source evidence during cleanup.
- Do not add dependencies, persistent subprocesses, GPU paths, or generic search modes without a measured need and exact-result equivalence tests.
- Do not keep duplicate backups or generated artifacts when they are reproducible from authoritative source evidence.
