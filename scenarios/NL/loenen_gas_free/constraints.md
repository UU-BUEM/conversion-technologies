# Gas-free neighborhood constraints — Loenen

Each constraint below states *what* must hold and *how* it's enforced
mechanically, since several of them aren't a Calliope `constraints:` block
at all — they're enforced earlier, by which technologies/carriers even
enter the model.

## Hard constraints

0. **Cooking is also a gas end-use, not just space heating/DHW — confirmed
   from real `buem` output, not assumed.** `buem`'s per-building annual
   summary carries a `cooking_gas_kWh` column (smoke-tested against 5 real
   Loenen buildings, Phase 1); it was 0.0 for all 5 test buildings, but the
   column existing at all means some Loenen archetypes may carry gas
   cooking load this scenario must also displace to stay genuinely
   gas-free, not just heating. Needs checking against the full 1,587-row
   run before Phase 3 (see `docs/phase1_demand.md`). This repo's registry
   has no "cooking" technology category at all today — out of scope for
   the conversion-technology side, but in scope for whether the *demand*
   side of the model should route `cooking_gas_kWh` to an electric-cooking
   demand tech instead of silently zeroing it.
1. **No `natural_gas` carrier anywhere in the active model.**
   Enforced at the `ExportConfig.technology_ids` level (`config/config.py`),
   not inside Calliope: this scenario's export only ever requests the
   non-gas technology ids already in the registry —
   `boiler_electric_*`, `boiler_biomass_*`, `heat_pump_electric_*`,
   `heat_pump_geothermal_*`, `combined_heat_and_power_biomass_*` (household/
   building/community scale variants of each). `boiler_gas_*` and
   `combined_heat_and_power_gas_*` are simply never passed to `export()` —
   not present, not zero-capacity. This is stronger than a Calliope-side
   `flow_cap_max: 0`, which would still let the gas carrier exist in the
   model's carrier set.
2. **No new gas infrastructure, retroactively or at build time.** Follows
   directly from (1) — there is no gas technology in the model for the
   optimizer to invest in, at any node, at any point.
3. **Every node's heat demand must be fully served.** Standard Calliope
   `demand` technology balance (`sink_use_equals` on each node's heat
   `demand` tech, from the per-building hourly profile) — not a new
   constraint, just confirming no slack/unmet-demand technology is added
   to this model. If some nodes can't balance with proven non-gas
   technologies alone (e.g. undersized heat pump capacity ceilings — see
   `core/validation.require_scale_capacity`), the solve is meant to fail or
   flag infeasibility, not silently drop demand.
4. **Each household's heat pump/boiler/CHP capacity stays inside the
   scale ceiling this repo already validates** (`require_scale_capacity`
   in `core/validation.py`, keyed off the `household`/`building`/
   `community` scale column in `technologies.csv`) — i.e. no accidentally
   routing community-scale CHP capacity into a single household node.

## Soft / scenario-design constraints (not yet mechanized — decide when building `nodes/`)

5. **Electricity grid import per node/feeder is not assumed unlimited.**
   Moving every household off gas pushes heating load onto the electricity
   carrier; a real feasibility check needs a grid-capacity constraint per
   LV feeder, not just per building. `enerplanet/enerplanet-pylovo`
   (synthetic LV grid generator) is the natural source for this — not
   wired in yet. Until it is, treat any solve as "thermally gas-free" only,
   not yet validated against the actual electricity distribution grid.
6. **No pre-assigned technology mix.** Which households get a heat pump vs.
   biomass boiler vs. community CHP is left to the optimizer (cost-
   minimizing, subject to the capacity ceilings in (4)) — this scenario
   does not hardcode a technology per building. If a later analysis needs
   to force specific households onto specific technologies (e.g. "every
   listed monument building keeps biomass, never heat pump" for a
   heritage constraint), that's an additional per-node `flow_cap_max`
   override on top of this, not a change to constraint (1).
7. **Biomass supply is treated as unconstrained fuel for now.** Real
   biomass availability at ~1,600-household scale is a genuine
   sustainability question (competing land/feedstock use) this scenario
   does not yet model — `cost_flow_in` on `boiler_biomass_*`/
   `combined_heat_and_power_biomass_*` is the only limiting signal today,
   not a feedstock cap. Flagged here so it isn't mistaken for a resolved
   question later.

## What "gas-free" deliberately does *not* constrain

- It says nothing about CO2/primary-energy accounting — biomass and
  electricity-from-the-grid are both allowed even though neither is
  automatically zero-carbon. If a future version of this scenario wants a
  genuine decarbonization constraint (not just "no gas pipe"), that's a
  separate, explicit constraint to add, not implied by this one.
- It says nothing about cost. A gas-free solve may be far more expensive
  than the counterfactual gas baseline; this scenario reports that cost
  rather than constraining it.
