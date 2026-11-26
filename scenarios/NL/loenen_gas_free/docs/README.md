# Scenario docs: Loenen gas-free

Working log for this scenario — what's been checked, what each phase
actually found, and what's still open. Mirrors the parent repo's
`docs/` convention (reference material, not a `.claude/` internal note),
but scoped to this scenario since it spans multiple repos (`buem`,
`occupancy`, `weather`, `conversion-technologies`, `MEME`) that this
package alone doesn't own.

- `phase0_scaffold.md` — scenario folder layout, constraints, decisions made before any data was touched.
- `phase1_demand.md` — buem batch run against Loenen: environment checks, data checks, run log, output validation.
- `phase2_technologies.md` — non-gas technology export from this repo: which ids, what scale, validation.
- `phase3_nodes.md` — per-building node assembly (not started).
- `phase4_solve.md` — MEME/Calliope submission (not started).
- `phase4b_solve_0610_sizing.md`, `phase5_per_building_decomposition.md`, `phase6_ev.md` — combined-model memory wall, exact per-building split, EV variants.
- `tariffs_nl_2027.md` — 2027 consumer tariffs after net metering ends.
- `energy_community_workflow.md` — **design** for the region + ~200-member energy community: grid (provided network or pylovo), simulation, flexibility, community filter, per-feeder Calliope model, power-flow re-check.
- `phase7_grid.md` — workflow step 1: grid from a provided network, DSO open data (Liander) or pylovo; Loenen built from Liander (local only: licence).
- `phase8_demand_supply.md` — workflow step 2: demand and PV supply per building and Liander station for four scenarios (baseline, standard/advanced retrofit, EV 50%); cooling fixed in buem (window sizing, shading, ventilation).
- `phase9_community_pilot.md` — workflow steps 5-6 pilot: 20 members on one station, independent vs community vs community with the station limit; mapping to the EnerPlanET S1-S4 experiments and the Dutch legal routes.
- `../measures/` — sourced catalogue of Loenen's own measures, subsidies and shared assets (loenenenergie.nl); see its `README.md`.

Each phase file states, up front: what was checked, what passed, what
didn't, and what's blocking the next phase — not a narrative of how we
got there.
