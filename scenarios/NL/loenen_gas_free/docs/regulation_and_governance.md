# Regulation and governance: what the model implements

Status 2026-11-27. One place for every Dutch rule, policy target and
governance choice that touches the Loenen scenario: what the rule says,
whether the model implements it, where it is implemented, and how sure we
are of the facts. The details stay in the phase documents linked below.

Status labels used in the tables:

- **Implemented**: changes the model's equations or inputs today.
- **Documented**: the facts and the modelling route are written down, but
  no run uses them yet.
- **Not modelled**: deliberately out of scope for now.

## 1. Summary

| Rule or policy | Status | Where | Source quality |
| --- | --- | --- | --- |
| Energiewet: energy sharing between active customers | Documented (links to the hub exist; the member cost view that prices them does not) | §2, `docs/phase9_community_pilot.md` | Primary sources checked 2026-11-27 (see §2) |
| Energiewet: energy community (energiegemeenschap) as a legal entity | Not modelled (governance, no effect on the equations) | §2 | Primary sources checked 2026-11-27 |
| Collective generation with the SCE subsidy (the former postcoderoos) | Documented | §3 | Secondary summary, still to verify (issue #5) |
| End of net metering (salderingsregeling), 1 Jan 2027 | Documented (member view only) | §4, `docs/tariffs_nl_2027.md` | Supplier notice to a customer; government fact still to cite |
| Energy tax and VAT | Excluded on purpose (system view) | §5 | Convention, not a fact to verify |
| Grid capacity at the transformer station (congestion) | Implemented (community pilot) | §6, `docs/phase7_grid.md`, `docs/phase9_community_pilot.md` | DSO data under licence (local only) |
| Gas-free target | Implemented (no gas technology in the model) | §7, `constraints.md` | Local and provincial targets, `measures/context.csv` |
| Subsidies (ISDE, LEN, municipal, LEF fund) | Documented (catalogue only) | §8, `measures/` | Quoted from loenenenergie.nl, with URLs |
| Household connection limit (3x25 A) | Not modelled | `docs/phase9_community_pilot.md` open items | |

## 2. Energiewet (in force since 1 January 2026)

**What the law does, as relevant here.** The Energiewet replaced the
Elektriciteitswet 1998 and the Gaswet on 1 January 2026 (law: Stb. 2025,
12; implementing decree, the Energiebesluit: Stb. 2025, 347 and 348). It defines the *active customer*
(actieve afnemer), who may generate, store and sell electricity, and the
*energy community* (energiegemeenschap), whose main purpose is not profit.
It allows *energy sharing* (energiedelen): electricity an active customer
feeds in is allocated to other customers' meters.

**What is and is not possible yet.** In the law as it stands, sharing
works only when the supplier offers it and every participant is a customer
of that same supplier; suppliers are not obliged to offer it. Sharing with
free choice of supplier comes from the EU electricity market directive
(EMD); its transposition deadline was 17 July 2026, and the Dutch implementing
bill has been through public consultation (status to check). In August 2026 no supplier offered
sharing to households.

**How the model represents it.** Sharing is accounting over the public
low-voltage grid, not a cable. The community model therefore links each
member to a hub node (`base_tech: transmission`, lossless, free) that
holds the shared assets (`scripts/community/build_community.py`). Two
consequences follow from the law and are kept in the model:

- the power still flows over the public grid, so the station limit (§6)
  applies to shared kWh as to any other kWh;
- grid tariffs and energy tax still apply to shared kWh. The system view
  (§5) leaves them out by design, so the pilot's saving is an **upper
  bound**; the member view must charge energy tax on hub-to-member flows
  (issue #3).

**Governance, not modelled.** The legal form of the community (a
cooperative such as Energie Coöperatie Loenen U.A., see
`measures/context.csv`), membership rules and how a sharing price is
settled between members do not change the optimisation. The sharing price
is settled after the run, from the optimal flows (as in the EnerPlanET
experiments, `docs/phase9_community_pilot.md`).

Sources (accessed 2026-11-27):

- Energiewet, Stb. 2025, 12 and Energiebesluit, Stb. 2025, 347/348:
  <https://www.njb.nl/wetgeving/staatsbladen/energiewet/>,
  <https://www.njb.nl/wetgeving/staatsbladen/energiebesluit/>
- RVO, energy communities:
  <https://www.rvo.nl/onderwerpen/samenwerken-energiegemeenschappen>
- Netbeheer Nederland, Energiewet FAQ (December 2025):
  <https://www.netbeheernederland.nl/sites/default/files/2025-12/faq_energiewet.pdf>
- Eerste Kamer, government letter on sharing and the EMD deadline:
  <https://eerstekamer.nl/9370000/1/j4nvi0xeni9vr2l_j9vvkyblr2b3ny8/vmniih4r5wvt/f=/vmnhigv01pzu.pdf>
- Overstappen.nl, 26 August 2026 (no supplier offers sharing):
  <https://www.overstappen.nl/nieuws/halfjaar-na-de-energiewet-geen-enkele-leverancier-biedt-consumenten-energie-delen-aan/>

To check before citing in a paper: the article numbers for the active
customer, the energy community and energy sharing, and the status of the
EMD implementation bill.

## 3. Collective generation (SCE subsidy)

From a secondary summary, **not yet verified** (issue #5): a cooperative
owns the installation and sells its output to any supplier; members
living in the postcode area receive a per-kWh subsidy share for 15 years.

Modelling route: a community asset at the hub that exports (deck S4).
Not run yet. The existing Thomassen rooftop installation in Loenen is
listed in `measures/community_assets.csv`.

## 4. End of net metering (1 January 2027)

From 2027 every kWh imported is paid at the full retail price including
energy tax and VAT, and exports earn a feed-in price minus a variable
feed-in cost. Figures, source and the two cost views:
`docs/tariffs_nl_2027.md`.

Model: not used by any run yet. The system view prices import and export
at the hourly day-ahead price (`build_nodes.py --grid-price day_ahead`;
export as negative `cost_flow_in` on `demand_grid_export`). The 2027
consumer tariffs belong to the member view only.

## 5. Taxes, VAT and subsidies: the system view

Every run so far uses the **system perspective**: costs in EUR (real
2025) excluding VAT, energy tax, levies and subsidies (CLAUDE.md
convention 8; `energy_prices.csv`; `build_nodes.py`). Taxes and
subsidies are transfers inside the economy, so they do not change the
system optimum. They do change what a member pays and therefore who joins
and what they build; that is the **member view**, designed in
`docs/energy_community_workflow.md` and not implemented yet (issue #3).

Never mix the two views: the 2027 tariff figures are consumer prices, the
model's grid price is not.

## 6. Grid capacity (congestion)

The community pilot enforces, hourly, the transformer station's spare
capacity after the non-members' load: import <= limit - non-member load,
export <= limit + non-member load (`build_community.station_limits`,
`--no-station-limit` turns it off). The per-station limits come from the
DSO's congestion data, which is licensed: it stays in the git-ignored
`data/` folder and no figure derived from it appears in this repository
(`docs/phase7_grid.md`).

Not modelled: the household connection limit (3x25 A), network tariffs
for capacity, and a power-flow check of the optimised dispatch (workflow
step 7).

## 7. Gas-free target

The scenario is gas-free by construction: no technology with a
natural-gas carrier is exported into the model, so the optimiser cannot
build or use one (`constraints.md`, hard constraints 1-2). Local and
regional targets (Loenen energy neutral by 2050; the village's
"aardgasvrij(-ready)" plans) are recorded with sources in
`measures/context.csv`. No law currently obliges an existing dwelling to
disconnect from gas; the constraint is a scenario choice.

## 8. Subsidies and local funds

The national, municipal and local schemes (ISDE, the LEN subsidy, the
Apeldoorn insulation subsidy, the LEF revolving fund, the Interreg share
of the community battery) are recorded as quoted, with URLs, in
`measures/subsidy_schemes.csv`. They are transfers and enter only the
member view (§5).

## 9. Open items

- Verify the SCE facts and the Energiewet article numbers (issue #5).
- Member cost view: energy tax on shared kWh, 2027 tariffs, subsidies
  (issue #3).
- Repeat if the EMD implementation allows sharing with free choice of
  supplier: the model does not change, only the participation assumptions.
