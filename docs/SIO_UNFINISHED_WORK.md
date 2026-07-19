# Survivor.io Optimizer Unfinished Work

This is the restart and loop checklist. It contains only work that is still missing, blocked, or unverified. Each pass must implement the next source-backed item, run focused and full validation, remove completed entries, then repeat. A source-blocked item stays here instead of being guessed.

## Release blockers

- Run the focused Clan Expedition suite and complete repository suite on the current branch head after every implementation pass.
- Run the exact-runtime integration checks locally with the source-locked sIO bundle, not only the Python fallback available in GitHub Actions.
- Add immutable regression fixtures from several real accounts covering raw account assembly, all uptime fields, direct damage, evolved passives, final CE damage, refunds, and selector-chest conversions.
- Verify every public recommendation has a complete legal before-state and after-state plus a balanced gross/net conversion ledger.
- Keep pull request 3 in draft and unmerged until the current head is green and every non-source-blocked entry below is resolved.

## Mount puzzle and Tetris

- Connect puzzle inventory to the account/profile import path and return only the resulting exact mount component stats to CE scoring.
- Parse owned I, O, T, J, and L piece counts from structured account data.
- Map each owned puzzle piece to its exact source-supplied component stats; placement geometry itself must remain outside learned training features.
- Add screenshot-to-piece-count parsing with confidence values and manual correction; never silently guess an unclear piece.
- Add resumable/checkpointed deterministic search for inventories that exceed the current state budget.
- Compare the independent combination solver with sIO only if the omitted `tetris` or `mountPuzzles` worker chunks become available; worker parity remains unknown until then.

## Choice and selector chests

- Map real account/export field names for each choice chest to the generic exact `choice_chests` schema.
- Add source-backed reward-unit catalogs for each known selector chest; do not infer that every chest grants one unit.
- Support multiple chest types in one upgrade and preserve all Pareto-equivalent exact allocations when chest types have different opportunity costs.
- Add chain planning where a selector-chest conversion enables more than one legal exact upgrade, without enumerating pick-order permutations.
- Keep random chest expected value separate from guaranteed choice-chest combinations.

## Equipment, Astral Forge, Chaos Fusion, and Xeno Transmute

- Validate every item-specific irreversible warning against the current sIO UI text.
- Add exact legality for Xeno effect rerolls and condition rerolls.
- Add reroll costs only when an exact source table is available.
- Audit all legal item reconfigurations against the omitted sIO `items` worker if that worker becomes available.
- Replace the current nearest-frontier cap for directional two-slot reallocations with a measured safe search bound or a proof that it cannot hide the best CE result.

## Tech, Twinborn, Resonance, and Overload

- Generate legal support-part reassignment actions with offensive/defensive restrictions and slot-specific chip rules.
- Generate legal Twinborn mode switches and enforce one active mode per pair.
- Implement reserved-Legend, fodder, active-skill-count, and downgrade strategy constraints from the sIO Tech optimizer.
- Add support downgrade and disabled-below-gate transition tests.
- Compare with omitted `resonance` and `skills` workers if those chunks become available.
- Keep Overload levels without published resonance gates unreachable.

## Survivors, Teamwork, Synergy, and Harmony

- Generate legal Teamwork slot assignments and replacements.
- Generate Combat Harmony left/right survivor reassignment actions.
- Implement main-survivor, Harmony/teamwork-rest-group, per-survivor cap, minimum-core, and maximum-Synergy constraints.
- Add survivor reset, shard conversion, and refund ledgers from exact source tables.
- Add broader exact-runtime parity fixtures for survivor context, cooldown, and direct-damage functions.

## Pets and Xeno Pets

- Implement the normal-pet rarity merge graph from exact source data.
- Generate normal-pet assist-skill assignment actions.
- Generate Xeno active/support selection and awakening-power allocation actions.
- Add Xeno four-slot eligibility, empty-slot handling, skill replacement, and exact Elixir costs.
- Add dismiss/exchange loss certificates, including cookie or exchange losses where applicable.
- Compare with omitted `petsCores` and `petsSkills` workers if those chunks become available.

## Collectibles and Custom Collection Sets

- Add the complete universal collectible shard-cost table.
- Generate collectible star and edition upgrades from exact costs.
- Implement all Custom Collection Set layouts, depth/level gates, and unique-collectible restrictions.
- Generate legal Custom Collection Set reassignment and upgrade actions.
- Add Legend Collectible Deconstructor eligibility, exact returns, confirmation, and irreversible warnings.
- Compare with omitted `collectiblesStars` and `customSets` workers if those chunks become available.

## Mount progression outside the puzzle

- Add exact mount fusion rules and costs.
- Add exact mount refinement rules and costs.
- Add exact mount reroll rules and costs.
- Add every reset/refund path with a balanced ledger.

## Input reading and account import

- Build the sIO ID/account-data import path and validate its schema against the exact runtime.
- Add aliases for source fields that still fail to map without changing their meaning.
- Add screenshot parsing for inventory sections with confidence scores and manual review.
- Reject incomplete profiles whenever a missing field could change the winner.
- Keep unknown fields losslessly through import, cleanup, action generation, and export.

## Calibration and evidence

- Collect repeated observed Clan Expedition runs for identical build and fight settings.
- Group residuals by exact build fingerprint and settings.
- Add enough real observations to detect systematic input/formula gaps without fitting hard mechanics to noisy runs.
- Keep rejected, contradictory, malformed, and duplicate evidence in append-only quarantine files.

## Training and recommendation logic

- Expand exact labeled before/after examples across every implemented action system.
- Add mandatory no-op/save-hold tests for every resource system.
- Add promotion tests proving a saved child cannot mutate or replace its immutable parent without all gates.
- Measure whether the learned proposal ordering actually reduces exact states evaluated; remove it if it provides no measured benefit.
- Keep learned models limited to proposal ordering. They cannot use Tetris placement geometry or choose a different final winner from exact CE damage.

## Final inconsistency and wasted-potential audit

- Re-scan every optimizer module for order-independent permutation search; allow ordering only where roles are genuinely directional and reversal changes the state.
- Re-scan for duplicate exact states before runtime scoring and report how many were removed.
- Profile action generation, JSON serialization, Node startup, and exact formula batching on realistic accounts.
- Remove unused legacy scenarios, dead heuristic ranking paths, duplicate data exports, and reproducible backups only after proving they are not source evidence.
- Review dependencies and new techniques only from measured bottlenecks; do not add complexity merely because a library or model is newer.
- Re-run source manifest, formula order, uptime, combination, training-leakage, focused, full-suite, and lineage audits at the final head.

## Source-blocked items

These cannot be completed from the supplied offline bundle and must not be fabricated:

- Omitted sIO worker implementations: `items`, `tetris`, `mountPuzzles`, `resonance`, `skills`, `petsCores`, `petsSkills`, `collectiblesStars`, and `customSets`.
- Exact mount fusion, refinement, reroll, and reset/refund cost tables not present in the supplied bundle.
- Exact Legend Collectible Deconstructor eligibility and return table not present in the supplied bundle.
- Exact Xeno Pet skill-swap/Elixir costs not present in the supplied bundle.
- Exact universal collectible shard/edition cost tables where the bundle supplies effects but not progression costs.
- Real-account regression fixtures and repeated CE observations that require user account exports or observed runs.

## Work that should not be added

- Do not add Ender's Echo, chapters, Path of Trials, Lunar Mine Expedition, Zone Operation, Operation Retreat, or Survivor Showdown to this CE optimizer.
- Do not enumerate permutations of identical Tetris pieces, selector-chest picks, item sets, or any order-independent inventory choice.
- Do not train on Tetris placement coordinates, rotations, boards, paths, search state counts, or solver internals; only exact resulting mount stats and CE labels may be used.
- Do not claim parity with omitted sIO worker algorithms.
- Do not invent costs, uptime, gates, legal transitions, reward units, or damage values.
- Do not use rarity points, generic breakpoint scores, community preference, or learned scores as the final winner.
- Do not delete source evidence during cleanup.
- Do not add dependencies, persistent subprocesses, GPU paths, or generic search modes without a measured need and exact-result equivalence tests.
- Do not keep duplicate backups or generated artifacts when they are reproducible from authoritative source evidence.
