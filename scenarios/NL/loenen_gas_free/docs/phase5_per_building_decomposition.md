# Phase 5 — Per-building decomposition: formulation, justification, and pipeline

## Abstract

The Loenen gas-free scenario's full-region energy-system optimization
problem, as formulated in Calliope over 1,260 single-dwelling nodes at
hourly resolution, is computationally intractable to construct as a
single combined linear program on commodity hardware: backend
construction exhibited unbounded memory growth under both Calliope 0.7.0
and 0.6.10, independent of solver choice. This document establishes,
from the scenario's own technology and topology definitions, that the
full-region problem is *block-diagonal* in the node index -- i.e.,
mathematically separable into one independent subproblem per building --
and that solving each subproblem independently and summing the results
is therefore exact, not an approximation. We give the formal argument,
the empirical evidence that motivated it, the one caveat (a candidate
shared electrical-network constraint) that would break separability if
introduced, and the resulting production pipeline
(`scripts/solve_single_building.py`, `scripts/solve_all_buildings.py`).

## 1. Problem statement

The full scenario, as exported by `calliope_export/modern.py` and
`calliope_export/ratio_math.py` into `technologies/export/
loenen_gas_free_techs.yaml` / `...additional_math.yaml`, together with
`nodes/nodes.yaml`, defines a linear program over:

- a node index $n \in N$, $|N| = 1260$ (one per single-dwelling
  building, per `data/loenen_single_dwelling_ids.txt`);
- a technology index $\tau \in T$, $|T| = 11$ per node (2 demand, 5
  household conversion techs, 4 supply techs; see `scripts/
  build_nodes.py`);
- a timestep index $t \in H$, $|H| = 8760$ (hourly, one year);
- decision variables: per-(node, tech) installed capacity
  $\mathrm{cap}_{n,\tau}$, and per-(node, tech, timestep) flow variables
  $\mathrm{flow}_{n,\tau,t}$ (in/out, per carrier), bounded by
  $\mathrm{cap}_{n,\tau}$.

The objective is total discounted cost, additively separable over $n$
and $\tau$ by construction (every `cost_*` parameter in
`technologies.csv`/`costs.csv` is a per-tech unit cost; nothing in
`core/technology.py` or `modern.py` introduces a cross-node or
cross-tech cost term).

## 2. Constraint structure: no coupling across $n$

Three constraint families could, in principle, couple nodes or
timesteps:

**(a) Node-to-node coupling via transmission.** Calliope represents
inter-node links via `links:` entries pairing nodes through a
transmission tech (e.g. the bundled `urban_scale` example's
`power_lines`/`heat_pipes`, which couple `X1,X2`/`X1,N1`/etc. through a
shared `energy_cap_max`). **`nodes/nodes.yaml` contains no `links:`
section** (confirmed by direct inspection: `grep -c "links:"
nodes/nodes.yaml` → 0). No such coupling exists in this scenario.

**(b) Intra-node coupling across timesteps via storage.** A storage
tech's state-of-charge variable links $\mathrm{flow}_{n,\tau,t}$ to
$\mathrm{flow}_{n,\tau,t-1}$, which would make node $n$'s own subproblem
non-separable *in time* (though still separable *across* nodes). **Every
tech in `technologies/export/loenen_gas_free_techs.yaml` has
`base_tech: conversion`, `demand`, or `supply`** (confirmed: `grep -c
"base_tech: storage"` → 0) -- no storage tech is present anywhere in
this scenario.

**(c) Intra-node coupling across timesteps via capacity sizing.** This
coupling *does* exist, and is retained: $\mathrm{cap}_{n,\tau}$ is
chosen once per $(n,\tau)$ and bounds $\mathrm{flow}_{n,\tau,t}$ for
every $t$. This ties timesteps together *within* one node's own
subproblem (as it must, to answer "what capacity should this building
install"), but never reaches across to a different node $n'$.

With (a) and (b) both absent and (c) confined within each node, the
full problem's constraint matrix is block-diagonal in $n$: no decision
variable or constraint belonging to node $n$ appears in any constraint
indexed by a different node $n'$.

## 3. Formal consequence

For a linear program
$\min \sum_{n} c_n^\top x_n$ subject to $A_n x_n \le b_n$ for each $n$
independently (no $x_n$ appearing in any $A_{n'}$, $n' \ne n$), the
global optimum equals $\sum_n \left(\min c_n^\top x_n \text{ s.t. } A_n
x_n \le b_n\right)$, and an optimal $x_n^*$ for each subproblem
concatenates to a global optimum. This is a standard property of
block-diagonal/separable LPs, not specific to Calliope or this
scenario -- stated here because it is the exact justification for
splitting the model, not an informal analogy.

**Consequence for this scenario**: solving the combined 1,260-node
model and solving each of its 1,260 single-node restrictions
independently, then summing total cost (and concatenating capacity/flow
results), are mathematically equivalent operations. Decomposition is
exact, not an approximation, a heuristic, or a reduced-order
substitute -- a direct consequence of (a) and (b) both being absent from
this scenario's own tech/topology definitions, verified from source
rather than assumed.

## 4. Empirical evidence corroborating the formal argument

Before formalizing the above, the practical path was empirical, and the
results corroborate the formal argument:

- The full combined model fails to `build()` under both Calliope
  versions tested (0.7.0, 0.6.10) at full node count and full-year
  timesteps, with unbounded memory growth (see
  `docs/phase4_solve.md` and `docs/phase4b_solve_0610_sizing.md`,
  Findings 1-6) -- consistent with the solver/backend attempting to
  construct a dense representation of a problem whose *size* scales
  with $|N| \times |T| \times |H|$ even though its true information
  content does not require that scale (no term couples two different
  $n$'s at once).
- A single node's own full-year subproblem solves cleanly: 27s wall
  clock, <1 GB peak memory, `calliope==0.6.10` + `appsi_highs`
  (`docs/phase4b_solve_0610_sizing.md`, Finding 7). This repo's own real
  scenario export (`calliope==0.7.0`, real `ratio_math.py` math, CBC)
  reproduces the same qualitative result: `bldg_8` alone solves in 57s.
- Running $N$ such single-node subproblems concurrently is genuinely
  parallel, not merely "not slower": 8 concurrent solves finished in
  44.9s wall-clock (vs. ~240s if run sequentially); 16 concurrent
  finished in 60.6s (vs. ~430s sequentially) (`docs/
  phase4b_solve_0610_sizing.md`, Finding 7). The real per-node export
  pipeline's own smoke test (`scripts/solve_all_buildings.py --limit 8
  --workers 8`) confirms the same pattern: 8 buildings, 49.2s, region
  total cost 17,471.08 -- the sum of 8 independent optimal node
  solutions.

## 5. The one caveat that would break separability

(a) above (no `links:`) is a fact about *this scenario's Calliope
formulation*, not a claim that the real-world electrical network behind
these 1,260 buildings has no shared capacity constraints. A synthetic
low-voltage grid for this same building population can be generated by
`enerplanet/enerplanet-pylovo` (lines/transformers with finite rated
capacity) and, in the wider `enerplanet` codebase, converted from a
solved Calliope model into a PyPSA network for a power-flow feasibility
check by `enerplanet/simulation-engine`'s `c2p` ("Calliope2PyPSA")
module -- confirmed by direct inspection of `c2p.py`: it reads a
*solved* Calliope model's results and builds/solves a separate PyPSA
power-flow problem from them.

Two things follow from checking `enerplanet/TentaCron` (the
org's actual workflow orchestrator) directly, rather than assuming:

1. **`TentaCron`'s own file tree contains zero references to Calliope,
   PyPSA, or `simulation-engine`** -- its two configured targets are
   `meme` and `buem`-gateway only. The `c2p`/PyPSA grid-feasibility path
   exists as code in the `enerplanet` organization but is not
   demonstrated to be part of the live, orchestrated production
   pipeline as of this writing.
2. Even if it were active: `c2p` consumes a Calliope model's results
   *after* Calliope has already solved, as an independent downstream
   power-flow check, not as a joint co-optimization that feeds
   constraints back into Calliope's own LP. Per-building decomposition
   therefore does not change what that downstream check would see --
   the aggregate per-timestep per-building flows Calliope produces are
   identical whether obtained from one combined solve or $N$ independent
   ones (Section 3). If grid-capacity feasibility ever needs to
   constrain *technology sizing itself* (e.g. capping a heat pump's
   electrical capacity because the local transformer cannot support
   it), that would require a new explicit link between the electrical
   carrier and a shared, node-grouped capacity constraint -- which would
   reintroduce coupling of type (a) above, and decomposition would need
   to be revisited for the affected node groups (e.g. one LV feeder's
   worth of buildings solved jointly, rather than all 1,260
   independently). Not needed today; flagged for whoever activates
   that check.

## 6. Resulting pipeline

- **`scripts/solve_single_building.py <node_id>`**: builds a one-node
  model from this scenario's own real `technologies/export/
  loenen_gas_free_techs.yaml` + `...additional_math.yaml` (the real,
  already-fixed `ratio_math.py` carrier-ratio constraints -- not a
  simplified stand-in schema) and that one node's own slice of
  `nodes/demand_heat.csv`/`demand_elec.csv`, builds, and solves with a
  real Calliope install. Returns installed capacities and total cost
  for that building alone.
- **`scripts/solve_all_buildings.py [--workers N] [--limit M]`**: calls
  the above for every node in `nodes/nodes.yaml` (or the first `M`, for
  a smoke test) in a `ProcessPoolExecutor` with `N` parallel workers,
  sums total cost across all solved buildings, and writes one combined
  JSON (`outputs/all_buildings_results.json`) with every building's own
  result plus the region total. One building's solver failure is
  caught and reported, not allowed to abort the batch (Section 3's
  separability means every other building's result remains exactly
  correct regardless).

Both verified working end-to-end against this scenario's real export
and a real `calliope==0.7.0` + CBC install (not just the earlier,
simplified 0.6.10 scale-probe scenario): `bldg_8` alone solves in 57.5s;
an 8-building smoke test via `solve_all_buildings.py --workers 8 --limit
8` solves in 49.2s wall-clock, region total cost 17,471.08 (the exact
sum of the 8 buildings' own optimal costs, per Section 3).

## 7. What this does and does not resolve

**Resolved**: full per-building hourly, full-year resolution is now
achievable without time-series clustering and without the memory wall
that blocked the combined-model approach, given this scenario's
confirmed-absent node/storage coupling.

**Resolved (2026-10-28)**: the first full 1,260-building batch run
(`outputs/all_buildings_results.json`, 16 workers) came back with 1,232
solved and 28 failed. Investigating all 28 found two distinct, unrelated
causes, neither a flaw in the decomposition argument above:

1. **10 `cbc.exe -stop` timeouts** -- resource contention from running 16
   concurrent CBC processes on one machine. Confirmed by retrying the
   same 10 buildings alone with 4 workers: all 10 solved cleanly. Not a
   correctness issue; a concurrency-tuning one (see Section 6's pipeline
   note on `--workers`).
2. **18 genuine infeasibilities** (`Termination condition: infeasible`,
   confirmed directly on `bldg_35`, not a flaky/transient result) -- the
   household-scale techs' combined `flow_cap_max`
   (`boiler_electric_household` 12 + `boiler_biomass_household` 15 +
   `heat_pump_electric_household` 10 + `heat_pump_geothermal_household`
   10 + `chp_biomass_household` 5 = 52 kW) is a hard *nameplate* ceiling
   on how much heat these 1,260 buildings' uniformly-assigned
   household-scale fleet can ever deliver at any single node. All 18
   failing buildings are exactly the 18 highest peak-heat-demand
   buildings region-wide (50-64 kW vs. a 14 kW region median) --
   `scripts/build_nodes.py` assigned every node the same household-scale
   tech list regardless of that node's own peak demand, so these 18
   outliers were asking for more heat than their own node could ever
   physically supply. Fixed in `scripts/build_nodes.py`: any node whose
   peak heat demand exceeds 90% of the household-scale combined ceiling
   (a safety margin added after 4 of the 18 cleared the strict >52 kW
   test but still proved infeasible, likely ratio-math/efficiency losses
   eating into the nameplate ceiling) also gets the building-scale techs
   (`*_building`, ceiling 100+60+80+100+80 = 420 kW) added -- not
   substituted, so the optimizer still freely mixes household + building
   equipment. All 28 originally-failed buildings solve after this fix
   (verified individually, then the full batch was rerun).

**Final result (2026-10-28)**: with the `build_nodes.py` fix applied,
**all 1,260/1,260 buildings solve** -- `outputs/all_buildings_results.json`
now has `n_solved: 1260`, `n_failed: 0`, `region_total_cost:
2050572.18`. The full rerun (12 workers) still hit 2 `cbc.exe -stop`
timeouts (contention, same pattern as the 10 above, not correctness);
both solved cleanly standalone and were merged in by hand. 16 workers
produced more contention-timeouts than 12 did across these reruns (10
vs. 2, on comparable node counts) -- `--workers 8-12` is the better
default on this machine, not 16, when running the full population.

**Not resolved by this document**:

- Supply-side prices (`supply_grid_electricity`/`supply_biomass`'s
  `cost_flow_out`) remain placeholders, not sourced from a real Dutch
  tariff -- a data problem, independent of the formulation question
  this document addresses. See the project's own `build_nodes.py`
  comments and the follow-up to source from CBS/ACM/Eurostat or
  published literature.
- Whether `enerplanet`'s production pipeline will, in the future,
  activate a grid-feasibility check that feeds back into technology
  sizing (Section 5) -- if so, the affected buildings (likely grouped
  by shared LV feeder/transformer, from pylovo's topology) would need
  to be solved jointly again, not independently.
