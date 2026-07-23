# Source-Locked Effect Preflight

## Purpose

The exact sIO Clan Expedition runtime remains the only final damage judge. The effect preflight runs first to reduce wasted exact evaluations and to explain why an effect matters for the current build.

It answers questions such as:

- Is +10 percentage points of `atkPercent` better than +5,000 `atkFinal` for this account?
- Does a `poisoned` bonus do anything when `poisonedUptime` is zero?
- Which multiplicative bucket changed: Skill Damage, Vulnerability, Boss Damage, direct skill damage, or the ATK bucket?
- Is an effect unknown to the source-backed formula and therefore required to go to the exact runtime?

## Source contract

The dependency graph is stored in `knowledge/sio_effect_dependencies.json` and is locked to sIO bundle SHA-256:

`7665a1d4ad479f799b9360347dad98ffdca8125d35c6fb0072c68343708c847d`

The important source relationships are:

| Effect | Required source or uptime | CE formula bucket |
|---|---|---|
| Poisoned | `poisonedUptime` | Poison + Weaken + Chill + Exposed |
| Weakened | `weakenedUptime` | Poison + Weaken + Chill + Exposed |
| Chilled | `chilledUptime` | Poison + Weaken + Chill + Exposed |
| Laceration | `lacerationUptime` | Laceration + Divine Fire |
| Divine Fire | `divineFireUptime` | Laceration + Divine Fire |
| Shield Damage | `shieldDamageUptime` | Shield Damage |
| Void Necklace | `voidNeckBoostUptime` | Void Necklace effective multiplier |

These relationships come from sIO modules 37013, 24804, and 67727. The ATK comparison uses the module-67727 ATK bucket, not a generic percentage-versus-flat shortcut.

## Exact-safe suppression rules

A legal action skips the original exact runtime only when all of the following are true:

1. Its system is explicitly covered by the source-backed Python assembly.
2. The action declares an exact after-state and source modules that intersect the coverage declaration.
3. The source-backed CE fallback calculates zero damage change.
4. No known CE formula bucket changes.
5. No unknown normalized formula field changes.

Tech, Twinborn, Overload, unclassified systems, missing-source actions, and estimator failures are never suppressed. They remain in the original exact runtime batch.

## Output

Each exact-scored candidate contains `preflight_estimate`, including changed effects, dependencies, active or inactive status, estimated damage gain, and changed formula buckets.

Each optimization result also contains:

- `effect_preflight.attack_option_comparison`
- `effect_preflight.effect_dependencies`
- `effect_preflight.ordered_estimates`
- `preflight_neutral_actions`
- `numeric_backend.source_proven_states_skipped`

The final recommendation is still sorted only by exact before-and-after sIO Clan Expedition damage.
