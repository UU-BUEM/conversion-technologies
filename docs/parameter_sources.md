# Parameter sources

Every number in `src/conversion_technologies/new/technologies.csv` and
`costs.csv` is traceable to a published source, or explicitly labelled as a
modelling assumption. `tests/test_parameter_sources.py` enforces this:

- every non-blank numeric cell has a row in
  [`sources/parameter_sources.csv`](sources/parameter_sources.csv);
- every such row matches the catalogue value exactly;
- every row names a `source_id` listed in [`sources/references.csv`](sources/references.csv)
  (unless its `basis` is `assumption`), and says where in the source the value is;
- every `proxy` row explains why a proxy was needed.

Changing a value in one place but not the other fails the test suite.

## Files

| File | Content |
| --- | --- |
| [`sources/references.csv`](sources/references.csv) | One row per source: publisher, title, version, URL, access date, what it is used for, and its price basis |
| [`sources/parameter_sources.csv`](sources/parameter_sources.csv) | One row per catalogue value: `value`, `unit`, `basis` (`direct` / `derived` / `proxy` / `assumption`), `source_id`, `source_item` (sheet, parameter, year), the raw `source_value` and `source_unit`, `price_year`, the `conversion` applied, and a `note` |
| [`sources/rvo_isde_heat_pumps_2026-11.csv`](sources/rvo_isde_heat_pumps_2026-11.csv) | The Dutch heat pump market database: all 2,843 models on RVO's ISDE list of November 2026 (meldcode, manufacturer, model, heat output, 2026 subsidy, refrigerant and GWP, category) |
| [`sources/rvo_isde_heat_pumps_2026-11_summary.csv`](sources/rvo_isde_heat_pumps_2026-11_summary.csv) | Per category: number of models, heat output percentiles, subsidy range |
| [`../tools/rvo_heat_pumps_to_csv.py`](../tools/rvo_heat_pumps_to_csv.py) | Rebuilds both RVO files from RVO's monthly Excel release |

## Conventions

- **Currency and price basis**: EUR, real 2025 prices, **excluding VAT and
  other taxes**, and excluding subsidies. This is a system (societal)
  perspective, consistent with the Danish Energy Agency catalogues, which
  publish on exactly this basis.
- **Price-year conversion**: euro-area HICP (Eurostat `prc_hicp_aind`, EA20,
  all items, 2015 = 100): 2015 = 100.00, 2020 = 105.05, 2025 = 128.76. So
  EUR2020 x 1.2257 and EUR2015 x 1.2876.
- **Per-unit to per-kW**: the DEA individual-heating data sheets give
  investment and fixed O&M per installed unit of a stated size (for example
  a 7 kW air-to-water heat pump). The catalogue stores cost per kW of the
  technology's primary output, so it divides by that reference size. Fixed
  per-unit costs are therefore spread linearly over capacity, which is the
  usual simplification in a linear optimisation model.
- **Interest rate**: 2.25 % real, the Dutch risk-weighted standard discount
  rate for social cost-benefit analysis (Werkgroep Discontovoet 2020,
  adopted by the cabinet on 27 October 2020).
- **Fuel and electricity prices are not in the catalogue**: `cost_flow_in`
  is blank everywhere. Energy is priced once, on the model's supply
  technology (for Loenen: `scenarios/NL/loenen_gas_free/energy_prices.csv`).

## Which source covers which row

| Scale | Heating technologies | Cooling technologies | CHP |
| --- | --- | --- | --- |
| household | DEA Individual Heating, *single-family house, existing building* (2025) | HRE D3.2 *split <5 kW* (compression); DEA *air-to-air heat pump* (reversible) | DEA micro gas turbine (proxy); DEA 3 MW_e pellet CHP (proxy) |
| building | DEA Individual Heating, *apartment block, existing building* (2025) | HRE D3.2 *air-cooled chiller <400 kW*; HRE *VRF* (reversible) | DEA micro gas turbine; DEA pellet CHP (proxy) |
| community | DEA Electricity and District Heating (1 MW heat pump, 5 MW electric boiler, gas and pellet heat-only boilers) | HRE D3.2 *air-cooled chiller >400 kW*; *500 kW LiBr absorption chiller* | DEA gas engine; DEA 3 MW_e pellet CHP |

Electric-vehicle rows (`category = ev`) have no Danish Energy Agency
source: the AC home charger cost is derived from ANWB's installed-cost
figure (EUR 2,000 incl. VAT for 11 kW), the building AC charge points
borrow it (proxy), the DC hub uses Virta's charger-only figure of about
200 EUR/kW (proxy; grid connection excluded), the charging efficiency is
Brady & O'Mahony (2016), and the V2G battery-wear cost is BloombergNEF's
2024 battery-electric-vehicle pack price (USD 97/kWh) divided by an
assumed 2,000 equivalent full cycles. The V2G hardware premium, every
lifetime and the battery size and reserve are assumptions; each row's
`note` in `parameter_sources.csv` says so.

The Danish Energy Agency's *Technology Catalogues* (costs and performance)
and *Socio-economic calculation assumptions* (fuel prices) are the
parameter sources. *Denmark's Climate Status and Outlook* is a projection
report and has no technology parameters.

## Derivations

- **Heat pump quality factor** (`efficiency`): the model computes COP as
  `efficiency x T_sink / (T_sink - T_source)` at a design point (air
  2 -> 45 degC, ground 10 -> 45 degC). The quality factor is calibrated so
  that this design-point COP equals the source's annual-average COP/SCOP.
  For example, DEA's 3.3 for a single-family air-to-water heat pump gives
  3.3 / 7.399 = 0.446. The design temperatures are assumptions, but the
  resulting COP is the source value.
- **Chiller COP**: HRE D3.2 gives the *standard* SEER of units sold in
  2020 and 2030. The catalogue takes their mean for 2025 and multiplies by
  0.7, because HRE §4.4 reports that real installations reach 60-80 % of
  the standard SEER. For example, split <5 kW: (6.6 + 7.8) / 2 x 0.7 = 5.04.
- **CHP heat efficiency**: where DEA gives only the electrical efficiency
  and the Cb coefficient (power-to-heat ratio), heat efficiency =
  electrical efficiency / Cb. For the gas engine: 0.47 / 0.99 = 0.475.
- **CHP ramping**: every DEA CHP unit starts within 0.5 h, below the
  model's 1 h timestep, so `flow_ramping = 1` (no hourly ramp limit).
- **Variable O&M**: where DEA gives it (district-heating chapters), it is
  stored as `cost_flow_out` per kWh of output. For CHP it is omitted,
  because one `cost_flow_out` would apply to both output carriers.
- **Older DEA chapters** (gas boiler, pellet heat-only boiler, gas engine,
  micro gas turbine, pellet CHP) give their first values for 2030, in
  EUR2020. The 2030 value is used as the 2025 value and inflated with the
  HICP.

## Proxies (`basis = proxy`)

These rows have no source at their own scale and borrow data from another
scale or technology. Each row's `note` says why.

| Row | Proxy used | Consequence |
| --- | --- | --- |
| `chp_gas_household` | DEA micro gas turbine (about 100 kW_e scale) | Small-scale cost likely underestimated |
| `chp_biomass_household`, `chp_biomass_building` | DEA 3 MW_e pellet CHP | Cost strongly underestimated, so excluded from the Loenen scenario |
| `chiller_absorption_household`, `chiller_absorption_building` | HRE 500 kW absorption chiller | HRE calls small absorption units prohibitively expensive, so excluded from the Loenen scenario |
| `chiller_heat_pump_reversible_community` | HRE air-cooled chiller >400 kW | Cooling mode only |
| `heat_pump_geothermal_community` | DEA 1 MW waste-heat heat pump | No ground-source district heat pump in DEA |

## Remaining assumptions (`basis = assumption`)

- **Per-node capacity ceilings** (`flow_cap_max`): these are modelling
  constraints (the most of one technology a single node may install), not
  product ratings. The exception is the household heat pumps, which use the
  90th percentile of heat output of ISDE-eligible models on the RVO list:
  air-to-water 19 kW, ground-source 29 kW. Every ceiling and every
  capacity cost is per kW of the technology's **primary output**; the
  exporter indexes them on that carrier because Calliope 0.7 would
  otherwise apply them to input carriers too (see
  `calliope_schema_mapping.md` "Capacity is per carrier").
- **Heat pump design temperatures** (see above).
- **Absorption chiller parasitic electricity** (`aux_electricity_ratio`,
  0.02-0.03): HRE includes pump work in its COP definition but gives no
  separate figure.
- **HRE D3.2 price year**: the deliverable (2017) does not state one.
  2015, the study's base year, is assumed and inflated to 2025. If the
  values are in fact nominal for each year, cooling costs are about 29 %
  too high.

## The RVO ISDE heat pump database

RVO's *Meldcodelijst Warmtepompen* is the official list of heat pumps
eligible for the Dutch ISDE subsidy, updated monthly. It contains **no
purchase prices**: for each model it gives the heat output, the 2026
subsidy amount, the refrigerant and its GWP, and the category. The
catalogue uses it for:

1. **Household heat pump capacity ceilings**: the 90th percentile of heat
   output, air-to-water 19 kW (n = 2,202) and ground-source 29 kW (n = 226).
2. **A household-perspective variant** (not used in the current system
   perspective): the 2026 subsidy follows a simple pattern. Air-to-water is
   about EUR 1,025 + EUR 225 per kW (1 kW: EUR 1,250; 68 kW: EUR 16,325).
   Ground-source has a floor of about EUR 4,200-4,425, then adds about
   EUR 150 per kW above roughly 12 kW. Subtracting it from the investment
   gives a household's net cost.

To refresh: download the new Excel file from
<https://www.rvo.nl/subsidies-financiering/isde/meldcodelijsten/warmtepompen>
and run `python tools/rvo_heat_pumps_to_csv.py <file.xlsx> <yyyy-mm>`. This
needs `openpyxl`, which is deliberately not a package dependency.

## Updating a value

Change the value in `technologies.csv` or `costs.csv` **and** its row in
`sources/parameter_sources.csv` (value, raw source value, conversion), and
add the source to `sources/references.csv` if it is new. Run `pytest`.
