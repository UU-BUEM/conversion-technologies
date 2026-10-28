# Phase 0 — scaffold

**Status: done.**

- `scenarios/NL/loenen_gas_free/README.md` — cross-repo data-flow table
  (buem/occupancy/weather/conversion-technologies/MEME), layout, and the
  per-building (not clustered) resolution decision.
- `scenarios/NL/loenen_gas_free/constraints.md` — the gas-free constraint set:
  hard-excluded gas technology ids at `ExportConfig` level (not a
  Calliope-side zero-capacity constraint), demand balance, per-scale
  capacity ceilings; flagged-but-not-yet-mechanized grid-capacity
  (`enerplanet-pylovo`) and biomass-feedstock limits.
- `.gitignore` updated: `scenarios/*/data/*` and `scenarios/*/outputs/*`
  ignored (regenerated from upstream repos / Calliope solves), `.gitkeep`
  tracked so the folders exist in a fresh checkout.
- Empty `data/`, `technologies/`, `nodes/`, `outputs/` folders created.

No code written yet; nothing to validate.
