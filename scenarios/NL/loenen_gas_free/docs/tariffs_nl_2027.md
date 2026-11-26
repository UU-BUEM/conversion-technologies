# Dutch household tariffs from 1 January 2027 (input for the PV and price discussion)

**Status: recorded, not yet wired.** `energy_prices.csv` and
`scripts/build_grid_price.py` still use the 2025 system-perspective price.
This note collects what changes in 2027 so the scenario can adopt it.

## Source

A Vattenfall customer notice for a variable household contract (received
November 2026), effective 1 January 2027. It is one supplier's notice, not
a national tariff: delivery rates and feed-in terms differ per supplier;
the end of net metering and the energy-tax changes apply to everyone.

## What changes on 1 January 2027

| Item | Electricity | Gas |
| --- | --- | --- |
| Variable delivery cost | up | up |
| Energy tax per unit | down (per kWh) | up (per m³) |
| Energy-tax reduction (fixed credit per connection) | down slightly | -- |
| Network (system operator) cost | changing, rates not yet known | changing, rates not yet known |
| Fixed delivery cost | unchanged | unchanged |

Supplier's example for an average household (2,430 kWh electricity and
1,040 m³ gas per year, Milieu Centraal): +EUR 215/yr electricity,
+EUR 381/yr gas. Reason given: higher wholesale gas prices (Middle East),
which also raise electricity prices.

## Net metering ends (salderingsregeling)

From 1 January 2027 imports and exports are no longer netted:

| Item | Value |
| --- | --- |
| Every kWh taken from the grid | full supply rate including energy tax and VAT |
| Feed-in tariff, every kWh exported | EUR 0.125900/kWh |
| Variable feed-in cost (replaces the former fixed feed-in cost) | EUR 0.060500/kWh incl. VAT |
| **Net revenue per kWh exported** | **EUR 0.0654/kWh** |

So self-consumption is worth the full retail rate, and export about
EUR 0.065/kWh: PV sizing and EV/heat-pump timing now favour using solar
power on site.

## How it maps onto the Loenen model

1. **Choose the cost perspective first.** The scenario's grid price
   (`energy_prices.csv`, EUR 0.26035/kWh) is the **system** perspective:
   energy + network, no energy tax, no VAT (Eurostat band DC). The 2027
   figures above are **consumer** prices (feed-in tariff, feed-in cost
   incl. VAT, energy tax). Mixing them misstates the value of export.
   Options:
   - consumer perspective: import = retail price incl. energy tax and VAT
     (2027 rates, network part still unknown), export revenue EUR 0.0654;
   - system perspective: import as now, export valued at the wholesale
     (day-ahead) price of that hour, the 2027 consumer terms as a
     sensitivity.
2. **Export in Calliope 0.7.** Add a sink technology on `electricity`
   at every node with PV, e.g. `export_grid` (`base_tech: demand`,
   `sink_use_max` unbounded or limited by the connection), with a negative
   `cost_flow_in` equal to the export revenue (-0.0654 EUR/kWh in the
   consumer case). Without it PV can only serve the building's own load
   (a one-node check built 1.24 of 4.8 kWp).
3. **Import price 2027.** Variable delivery up, energy tax per kWh down,
   network rates unknown: a sourced 2027 price (e.g. Eurostat once
   published, or the 2027 energy-tax rates plus supplier delivery rates)
   replaces 2025 in `energy_prices.csv` and `build_grid_price.py`.
4. **Gas.** Not used in the gas-free scenario; relevant for a gas
   reference case (energy tax per m³ up).

PV technology and profiles: conversion-technologies
`docs/generation_technologies.md` (`pv-profile` command; roof faces from
buem's `roof_faces` summary column after a Phase 1 rerun).
