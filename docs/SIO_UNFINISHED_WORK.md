# Survivor.io Optimizer Unfinished Work

This file contains only work that cannot be completed honestly from the repository and the supplied offline sIO bundle. Completed work must not be re-added here. A blocked item stays unknown until its exact source, account data, or observation set is supplied.

## Final verification still required

- Run the focused exact Clan Expedition suite from the runnable CI snapshot with the source-locked user sIO bundle.
- Confirm the final branch head passes the formula/uptime audit, combination/training-leakage audit, focused Python 3.11 and 3.12 suites, complete Python 3.12 suite, and champion-lineage smoke test.
- Keep pull request 3 unmerged until those final checks finish.

## Missing sIO source data or worker code

The supplied bundle registers these workers but does not include their executable chunks:

- `items`
- `tetris`
- `mountPuzzles`
- `resonance`
- `skills`
- `petsCores`
- `petsSkills`
- `collectiblesStars`
- `customSets`

The bot may independently enumerate exact states, but it must not claim parity with an omitted worker.

## Equipment and Xeno Transmute blockers

- Exact Xeno effect-condition reroll legality.
- Exact reroll costs.
- Item-specific irreversible-warning text from the current sIO UI.
- Direct parity comparison with the omitted `items` worker.

## Tech and Resonance blockers

- Full support-part reassignment search matching the omitted `resonance` and `skills` workers.
- Complete source rules for reserved Legend parts, fodder strategies, active-skill-count strategies, and downgrade strategies.
- Worker-parity versions of Fast, Normal, and Full Tech search.
- Resonance gates beyond the published Overload 16 table. Levels with unpublished gates must remain unreachable.

## Survivor progression blockers

- Exact Survivor level-resource cost table where it is not published in the supplied bundle.
- Exact Survivor reset, shard-conversion, and refund tables.
- Real-account runtime fixtures for broader Survivor context, cooldown, and direct-damage parity.

## Pet and Xeno Pet blockers

- Exact normal-pet rarity merge graph.
- Exact normal-pet assist-skill assignment rules.
- Exact Xeno awakening-power allocation rules.
- Exact Xeno four-slot/empty-slot skill eligibility and Elixir swap costs.
- Exact dismiss/exchange return and loss tables, including cookie losses.
- Direct parity comparison with omitted `petsCores` and `petsSkills` workers.

## Collectible blockers

- Complete universal collectible shard costs.
- Complete collectible edition-upgrade costs.
- Exact Custom Collection Set layout, depth, level, and unique-collectible legality tables.
- Exact Legend Collectible Deconstructor eligibility and return table.
- Direct parity comparison with omitted `collectiblesStars` and `customSets` workers.

## Mount blockers

- Exact mount fusion rules and costs.
- Exact mount refinement rules and costs.
- Exact mount reroll rules and costs.
- Exact mount reset and refund tables.
- Exact source mapping from each owned puzzle piece to aggregate component stats.
- Direct parity comparison with omitted `tetris` and `mountPuzzles` workers.

## Account import and image-data blockers

- The authenticated sIO ID/account-export endpoint and its request/response contract.
- Real account exports needed to map remaining account field aliases.
- Inventory screenshots needed to build and validate confidence-scored screenshot parsers.
- Manual correction examples for unclear screenshot fields; the parser must not silently guess.
- Real choice-chest export fields and exact reward-unit catalogs. The generic combination engine accepts exact supplied options but does not invent chest contents.

## Calibration and training-data blockers

- Repeated observed Clan Expedition runs for identical builds and fight settings.
- Several real account snapshots for immutable raw-account regression fixtures.
- Exact before/after labels across source-blocked action systems.
- Enough real examples to measure whether learned proposal ordering saves exact evaluations. The public winner already ignores learned ordering.

## Current contract boundaries

- The public optimizer recommends the best exact legal **next action** and ranked exact alternatives. It does not claim to solve an unlimited multi-action future spending portfolio.
- An exact configuration search that exceeds its declared state budget withholds the global recommendation instead of presenting a partial winner.
- Choice chests are evaluated as canonical multiset allocations for each exact next action. Pick order is never enumerated.
- Teamwork is an unordered combination. Main Survivor, Harmony left/right, Twinborn tech identity, and distinct Xeno support skill roles remain directional because changing those roles changes the state.
- Mount placement geometry is deterministic solver output and never a learned feature. Only verified aggregate mount component stats may reach CE scoring or training labels.

## Work that must not be added

- Do not add Ender's Echo, chapters, Path of Trials, Lunar Mine Expedition, Zone Operation, Operation Retreat, or Survivor Showdown to this CE optimizer.
- Do not enumerate permutations of identical Tetris pieces, selector-chest picks, interchangeable Teamwork members, identical Xeno support roles, item sets, or any other order-independent choice.
- Do not train on Tetris coordinates, rotations, boards, paths, state counts, or solver internals.
- Do not invent costs, uptime, gates, reward units, legal transitions, return values, or damage values.
- Do not claim parity with omitted sIO worker algorithms.
- Do not use rarity points, generic breakpoint scores, community preferences, or learned scores as the final winner.
- Do not delete source evidence during cleanup.
- Do not add dependencies, persistent subprocesses, GPU paths, or generic search modes without a measured need and exact-result equivalence tests.
- Do not keep duplicate backups or generated artifacts when they are reproducible from authoritative source evidence.
