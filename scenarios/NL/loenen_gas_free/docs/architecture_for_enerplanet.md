# Architecture for `enerplanet`: per-building decomposition for large-community solves

**Written for: an EnerPlanET developer evaluating `enerplanet/simulation-engine`'s
architecture for large communities.** This is the one idea from this
scenario worth carrying into `enerplanet` directly: a large community's
energy-system optimization does **not** need to be solved as one combined
model. It can be split into one independent sub-problem per building, solved
in parallel, and summed — and for this scenario's real topology, that split
is mathematically exact, not an approximation. Full derivation:
`docs/phase5_per_building_decomposition.md`. This document is the
high-level picture; that one has the formal argument and the empirical
evidence.

## Why this matters for `enerplanet`

A single combined Calliope model over this scenario's 1,260 buildings
(hourly, full year) never finished building, under **either** Calliope
0.7.0 or 0.6.10 — unbounded memory growth, no plateau, confirmed
independently of solver choice (`docs/phase4_solve.md`,
`docs/phase4b_solve_0610_sizing.md`). That is very likely a general property
of building one dense per-node/per-timestep LP at this scale, not a bug in
one Calliope version. Any `enerplanet` deployment aiming at full
per-building resolution for a real community will hit the same wall.

The per-building decomposition below sidesteps it entirely: the same full
community, full year, full hourly resolution solved in ~80 minutes on a
22-core development machine (extrapolated from a measured 16-way parallel
batch), each individual building's solve taking under 1 minute and well
under 1 GB of memory.

## The mechanism: one shared LP vs. N independent ones

A combined model puts every building's capacity-sizing variables inside one
shared backend build, which is exactly what grew unbounded in memory.
Nothing links one building's variables to another's in the real model
(`nodes.yaml` has no `links:` and no `storage` tech anywhere), so the split
below is exact, not an approximation:

![Combined model: one shared backend build for all buildings, unbounded memory
growth. Decomposed model: one independent model per building, solved in
parallel and summed.](figures/per_building_decomposition.svg)

*Why the split is free: `nodes.yaml` has no `links:` between buildings and
no `storage` tech anywhere. Every variable in the combined model's big
block already belongs to exactly one building — the block-diagonal
structure was in the problem the whole time, just hidden inside one shared
solve.*

## The pipeline

```mermaid
flowchart TD
    subgraph A["conversion_technologies (this repo's src/)"]
        A1["technologies.csv + costs.csv\n(per-technology capacity, efficiency/COP, cost inputs)"]
        A2["export-all\n(calliope_export/modern.py)"]
        A3["YAML catalog: boiler, heat pump,\nCHP, chiller x 3 scales"]
        A4["additional_math.yaml\n(ratio_math.py: fixed carrier\nratios, multi-carrier techs)"]
        A1 --> A2 --> A3
        A2 --> A4
    end

    subgraph B["scenarios/NL/loenen_gas_free (reads the generated YAML only)"]
        B1["buem hourly per-building data\n(Q_heat_kW, dhw_kW, elec_kW, Q_cool_kW)"]
        B2["build_nodes.py"]
        B3["One Calliope node per building\n(nodes.yaml + demand_*.csv)\nno links, no storage"]
        B1 --> B2
        A3 --> B2
        A4 --> B2
        B2 --> B3
    end

    subgraph C["Key structural fact (phase5): block-diagonal by node"]
        C1["No links, no storage:\nonly a node's own flow_cap\nties its timesteps together"]
        C2["=> combined N-node model = N\nindependent solves, summed (exact)"]
        C1 --> C2
    end
    B3 --> C1

    subgraph D["Execution: solve_single_building.py x N, in parallel"]
        D1["One building's full-year model\n(~1 min, <1 GB RAM)"]
        D2["ProcessPoolExecutor, 16 workers\n(solve_all_buildings.py)"]
        D3["Sum: region_total_cost,\nper-building flow_cap / tech choice"]
        D1 --> D2 --> D3
    end
    C2 --> D1
```

The scenario layer (B) is separately owned: it never imports
`conversion_technologies` as Python and consumes only its generated YAML.
Nothing ties one node's variables to another's, so solving the combined
model is mathematically equivalent to solving each building on its own and
summing the results.

A shareable, standalone version of both diagrams above (same content, no
repo access needed) is published at
<https://claude.ai/artifact/89vj4aGyYMaRSn8aSLGMMt> — that's the one to
actually send an EnerPlanET developer; this file is the versioned source
of truth it was built from.

## What to replicate inside `enerplanet`

1. **Don't build one combined LP for a large community.** If
   `enerplanet/simulation-engine` has (or is heading toward) a single
   `calliope.Model` spanning every building in a community, that is the
   exact shape that hit the memory wall here — worth checking before it's
   hit in production.
2. **Check the same structural precondition first**: does the real model
   have cross-building `links:` (shared electrical/heat network) or any
   `storage` tech? If **no** to both (as here), the decomposition above is
   exact and safe to use as-is. If the real community *does* need a shared
   network or storage, decomposition breaks down — that becomes the one
   thing that would force a combined solve (flagged, not solved, in
   `docs/phase5_per_building_decomposition.md` section on separability
   caveats).
3. **Parallelize at the building level**, not inside one solver call. Each
   building's sub-problem is small and fast; the speedup comes from running
   many of them concurrently (measured: 16 concurrent full-year solves
   finished in ~2.3x one solve's solo time, not 16x — real parallelism, not
   linear slowdown).
4. **The technology catalog (`conversion_technologies`) and the per-building
   topology (`scenarios/`) are already separated** on this side
   specifically so the catalog (per-technology YAML + cost/efficiency
   inputs) can be swapped or extended — e.g. the `chiller` category added
   for cooling — without touching how buildings are assembled into nodes,
   and vice versa. Worth keeping that same separation inside `enerplanet`'s
   own architecture if it doesn't already have it.

## Caveats carried over from the underlying docs (not re-litigated here)

- Calliope's own `additional_math.yaml` carrier-ratio constraints and this
  whole pipeline's output have been verified algebraically, not against a
  solve that printed a ground-truth cross-check from an independent
  source — see `docs/calliope_schema_mapping.md`'s standing caveat.
- The Calliope version is `calliope==0.7.0` (decided 2026-11-10; the
  `simulation-engine` Dockerfile's 0.6.10 pin is stale -- see the note at
  the top of `docs/phase4b_solve_0610_sizing.md`). Everything in this
  document about the decomposition's *validity* holds regardless of which
  version `enerplanet` ends up running, since it's a structural fact about
  the model (no links, no storage), not a Calliope-version-specific
  behavior.
