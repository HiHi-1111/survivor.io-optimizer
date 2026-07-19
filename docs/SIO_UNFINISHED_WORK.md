# Survivor.io Optimizer Unfinished Work

This file is the restart checklist. Keep only work that is still missing, blocked, unverified, or intentionally excluded. Remove an item only after its implementation and tests are committed.

## Release blockers

- Run the focused Clan Expedition suite and the complete repository suite after every remaining implementation change.
- Run the exact-runtime tests with the source-locked sIO bundle, not only the Python fallback.
- Keep pull request 3 in draft until every required check is green.
- Add regression fixtures from several real accounts so exact raw-account assembly, uptime, direct damage, evolved passives, and final CE damage are compared across updates.
- Verify that every public recommendation is produced from a legal complete before-state and after-state with a balanced resource ledger.

## Mount puzzle and Tetris

- Connect the combination-based puzzle solver to player profiles and the public optimizer.
- Parse owned I, O, T, J, and L piece counts from account data or inventory screenshots.
- Convert a selected puzzle placement into the exact component-stat totals consumed by mount CE scoring.
- Add an image-to-piece parser with confidence reporting and manual correction; do not silently guess unclear pieces.
- Add deterministic performance limits and continuation/checkpoint support for large inventories when exhaustive combination search exceeds the state budget.
- Compare the independent solver with known sIO outputs if the omitted `tetris` or `mountPuzzles` worker chunks become available.
- Keep worker parity marked unknown while those worker chunks are absent.

## Equipment, Astral Forge, Chaos Fusion, and Xeno Transmute

- Validate every item-specific irreversible warning against the source UI.
- Add exact legality for Xeno effect rerolls and condition rerolls.
- Add reroll costs only when the exact source table is available.
- Add every legal item reconfiguration that is still absent from the action generator.
- Verify that item search uses unique combinations of choices and never repeats equivalent slot/order permutations.

## Tech, Twinborn, Resonance, and Overload

- Generate legal support-part reassignment actions with offensive/defensive restrictions and slot-specific chip rules.
- Generate legal Twinborn mode switches and enforce one active mode per pair.
- Implement reserved-Legend, fodder, and skill-count strategy constraints from the sIO Tech optimizer.
- Add support downgrade and disabled-below-gate transition tests.
- Leave Overload levels without published resonance gates unreachable instead of extrapolating them.
- Compare the independent frontier search with the omitted sIO `resonance` and `skills` workers if those chunks become available.

## Survivors, Teamwork, Synergy, and Harmony

- Generate legal Teamwork slot assignments and replacements.
- Generate Combat Harmony left/right survivor reassignment actions.
- Implement group/rest allocation only after the exact constraints are mapped.
- Add survivor reset, shard conversion, and refund ledgers from exact source tables.
- Add broader parity fixtures for survivor context, cooldown, and direct-damage functions.

## Pets and Xeno Pets

- Implement the normal-pet rarity merge graph.
- Generate normal-pet assist-skill assignment actions.
- Generate Xeno active/support selection actions.
- Implement Xeno awakening-power allocation.
- Add Xeno skill slot eligibility, skill replacement, and Elixir costs.
- Add dismiss/exchange loss certificates, including cookie or exchange losses where applicable.
- Compare with the omitted `petsCores` and `petsSkills` workers if those chunks become available.

## Collectibles and Custom Collection Sets

- Add the complete universal collectible shard-cost table.
- Generate collectible star and edition upgrade actions from exact costs.
- Keep random-chest expected value separate from guaranteed progression.
- Implement all Custom Collection Set layouts, depth/level gates, and unique-collectible restrictions.
- Generate legal Custom Collection Set reassignment and upgrade actions.
- Add the Legend Collectible Deconstructor eligibility and return table.
- Compare with the omitted `collectiblesStars` and `customSets` workers if those chunks become available.

## Mount progression outside the puzzle

- Add exact mount fusion rules and costs.
- Add exact mount refinement rules and costs.
- Add exact mount reroll rules and costs.
- Add all reset/refund paths with balanced ledgers.

## Input reading and account import

- Build the sIO ID/account-data import path and validate its schema against the exact runtime.
- Add robust aliases for any source fields that still fail to map without changing their meaning.
- Preserve unknown fields so future sIO updates are not destroyed during cleanup.
- Add screenshot parsing for inventory sections with confidence scores and manual review.
- Reject incomplete profiles when a missing field could change the winner instead of filling it with a guessed value.

## Calibration and evidence

- Collect repeated observed Clan Expedition runs for the same build.
- Group residuals by exact build fingerprint and fight settings.
- Use observed damage only to detect formula/input problems; never let calibration overwrite hard mechanics.
- Keep rejected, contradictory, and malformed evidence in append-only quarantine files.

## Training and recommendation logic

- Expand exact labeled before/after examples across every implemented action system.
- Verify that inherited champion children cannot mutate or replace their parent without passing all promotion gates.
- Keep learned models limited to proposal ordering; they must never choose a different winner than exact CE damage.
- Add mandatory no-op and save/hold tests for every resource system.
- Add tests that equivalent combinations are deduplicated before formula scoring.

## Work that should not be added

- Do not support Ender's Echo, chapters, Path of Trials, Lunar Mine Expedition, Zone Operation, Operation Retreat, or Survivor Showdown in this optimizer.
- Do not enumerate permutations of identical Tetris pieces, item sets, or other order-independent inventory choices.
- Do not claim parity with omitted sIO worker algorithms.
- Do not invent costs, uptime, gates, legal transitions, or damage values.
- Do not use rarity points, generic breakpoint scores, or learned scores as the final winner.
- Do not delete source evidence during cleanup.
- Do not add dependencies, persistent subprocesses, GPU paths, or generic search modes unless a measured need justifies them and they preserve exact results.
- Do not keep duplicate backup data or generated artifacts in the repository when they can be reproduced from the authoritative sources.
