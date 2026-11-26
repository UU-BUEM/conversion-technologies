# Loenen sustainable-measures catalogue

What Loenen itself offers or plans: measures, subsidies, shared assets.
Collected from <https://loenenenergie.nl/>, the site of Energie Coöperatie
Loenen (ECL) and Stichting Loenen Energie Neutraal (LEN), together with the
Apeldoorn subsidy check and Gemeenteblad 2026 nr. 355914. Accessed 2026-11-25.

The catalogue records **what the sources say**. Using any of it in the model
is a separate, explicit step; see "Cost perspective" below and
`docs/energy_community_workflow.md`.

## Files

| File | One row per | Source of truth? |
| --- | --- | --- |
| `measures.csv` | measure, offering or programme (25) | yes |
| `subsidy_schemes.csv` | subsidy, fund or financing instrument (12), referenced from `measures.csv` | yes |
| `community_assets.csv` | shared asset, existing or planned (6), referenced from `measures.csv` | yes |
| `context.csv` | key/value facts: legal forms, targets, partners, net metering | yes |
| `loenen_measures.json` | all four tables, with schemes and assets nested under each measure | **no**: generated |

Edit only the CSVs, then regenerate and validate the JSON. Run from the
scenario root:

```bash
python scripts/build_measures_json.py          # validate + write loenen_measures.json
python scripts/build_measures_json.py --check  # validate only
```

The script checks enums, a `source_url` on every row, that numbers parse,
cross-references and unique ids. It uses the standard library only.

## Columns

**Shared conventions.** A blank cell means the source does not state the
value; nothing is estimated. Numeric columns use a plain `.` decimal
(`5000`, not `5.000`). Text columns keep the source's Dutch formatting, for
example `EUR 2.238,50`. `accessed` is the date the page was read.

### `measures.csv`

| Column | Meaning |
| --- | --- |
| `id` | slug |
| `name_nl`, `name_en` | name as on the site / English translation |
| `category` | `insulation`, `heating`, `hot_water`, `pv`, `storage`, `ev_mobility`, `collective_generation`, `heat_network`, `grid_flexibility`, `behaviour_saving`, `financing_subsidy`, `advice_service`, `other` |
| `level` | `household`, `building`, `community` |
| `status` | `offered`, `operating`, `planned`, `idea`, `past` |
| `target_group` | who may use it (owners, members, ...) |
| `cost_value`, `cost_unit`, `cost_vat` | price as quoted (often a worked example), its unit, VAT basis |
| `subsidy_scheme_ids` | `;`-separated ids from `subsidy_schemes.csv` |
| `savings_claim` | savings as claimed by the source (not verified) |
| `model_hook` | where the measure enters the modelling pipeline (below) |
| `model_status` | `exists` (a technology/input is already there), `needs_tech` (to be built), `out_of_scope` |
| `source_url`, `accessed`, `notes` | provenance and details |

`model_hook` values:

| Value | Meaning |
| --- | --- |
| `conversion_tech:<category>/<variant>/<scale>` | a row of `src/conversion_technologies/new/technologies.csv` |
| `generation_tech:<category>/<variant>/<scale>` | a row of `generation_technologies/technologies.csv` |
| `storage:<name>` | a storage technology (the home battery does not exist yet) |
| `community_asset:<id>` | a row of `community_assets.csv`, placed on a community node |
| `subsidy_scheme:<id>` | the measure *is* a financing instrument |
| `buem_envelope` | changes building demand through a buem envelope-retrofit variant |
| `tariff` | enters as an electricity price or contract (e.g. `grid_price_nl_2018.csv`) |
| `not_modelled` | no model counterpart planned |

### `subsidy_schemes.csv`

| Column | Meaning |
| --- | --- |
| `instrument` | `grant`, `grant_and_financing`, `repayment_obligation`, `voucher`, `member_bond`, `budget_subsidy_to_organisation`, `project_grant` |
| `rate_pct` | percentage; for bonds, the interest rate per year (see `base`) |
| `cap_eur` | maximum per measure, per home or per member |
| `amount_eur` | fixed amount (example amount where `notes` says so) |
| `base` | what the rate applies to: incl./excl. VAT, before/after other subsidies |
| `stacking` | which schemes it can be combined with |
| `eligibility`, `deadline` | conditions as stated |
| `status` | `offered`, `awarded`, `intended`, `closed`, `past` |

### `community_assets.csv`

Columns: `capacity_kw`, `energy_kwh`, `annual_yield_kwh`, `units` (text,
e.g. panel count), `investment_eur`, `financing`, `owner`, `location`.
`status` is one of `operating`, `planned`, `idea`, `past`.

## Cost perspective (read before using any number)

- **The catalogue holds consumer prices as quoted.** These are often worked
  examples and often include 21% VAT. The model's technology costs are
  *system perspective*: EUR, real 2025, excluding VAT and taxes (repository
  `CLAUDE.md`, hard convention #8). Turning a quoted price into a model cost
  is a separate, documented conversion step. It never happens silently.
- **Subsidies are transfers.** In a system-perspective run they cancel out
  and are left out. They enter only a *member/consumer-perspective* run,
  together with the 2027 consumer tariffs (`docs/tariffs_nl_2027.md`).
- **LEN's 37% applies to a notional VAT-inclusive base.** In the heat-pump
  example it is applied after the national ISDE amount has been deducted.
  The LEF repayment (50% of the expected savings) is a cash flow back to the
  fund, not a cost reduction.

## Known inconsistencies on the site

- **Thomassen rooftop.** One page gives 2,404 panels, EUR 690,000 and
  800,000 kWh, for "more than 300 households". The 2020 start article gives
  2,760 panels, EUR 700,000 and about 250 households. The homepage gives
  700–800 MWh. The kWp is not published anywhere.
- **Net metering.** The FAQ says it was extended "tot en met 2023". The rest
  of the site says it ends on 1 January 2027.
- **Battery opening.** The battery page says the date is not set yet. Another
  article reports an opening on 8 July 2026.
- **Partner counts.** The SmartCORE page lists 14 partners but its text says
  "Vijftien". The green-gas article says "Vijf partijen" but names four.
- **Wattflex.** The page is dated April 2022. The cooperative page says it is
  "expanding in 2026".

## Not yet read

Listed in the site's sitemap but not read:

- `verdien-aan-duurzame-stroom-uit-loenen/` (mentions a large battery licence)
- `naar-een-systeem-van-onderling-energie-delen-in-loenen/` (only its teaser is used)
- `veel-interesse-voor-het-slim-laden-van-de-auto/`
- `tijdelijk-noodfonds-energie-voor-lage-inkomens-met-hoge-energierekening/`
- `nieuwe-regelingen-voor-nieuwere-technieken/`
- the De Centrale participation agreement
- the BESS information memorandum PDF
- about 90 older news posts from 2014–2025

Read these before relying on the flexibility or energy-sharing rows.
