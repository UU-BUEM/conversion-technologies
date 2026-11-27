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
| Collective generation with the SCE subsidy (the former postcoderoos) | Documented | §3 | Primary sources (RVO) checked 2026-11-27 |
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

**Article numbers** (Energiewet as published, Stb. 2025, 12):

| Provision | Article |
| --- | --- |
| Definitions of *actieve afnemer*, *energiegemeenschap* and *delen van energie* ("zelfverbruik door één of meer actieve afnemers van hernieuwbare energie") | 1.1 |
| A market party may not stop a customer from producing for own use, sale or supply to others, or from participating in an energy community | 2.3(1)(a)-(b) |
| Statutes of an energy community: open and voluntary participation, right to leave, control by natural persons, small firms and local authorities | 2.4 |
| Right to share energy, on four conditions: (a) an energy-sharing contract with a supplier that offers it, (b) every participant has a supply or feed-in contract with that supplier, (c) a smart meter whose communication function is used, (d) sharing per imbalance settlement period; locality rules may follow by decree (2.30(2)) | 2.30 |
| Net metering (salderen) for small connections, not for shared electricity | 2.31 |

**What is and is not possible yet.** Article 2.30(1)(a)-(b) means that
sharing works only when the supplier offers it and every participant is a
customer of that same supplier; suppliers are not obliged to offer it.
Sharing with free choice of supplier comes from the EU electricity market
directive (EMD, Directive (EU) 2024/1711); its transposition deadline was
17 July 2026. The Dutch bill, the *Implementatiewet EMD-pakket*
(Kamerstuk 36990), was submitted to the House of Representatives on
7 July 2026; the committee's written report followed on 2 October 2026.
As of 27 November 2026 no plenary debate or vote has taken place and no
entry-into-force date is set. In August 2026 no supplier offered sharing
to households.

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

- Energiewet, Stb. 2025, 12 (text of articles 1.1, 2.3, 2.4, 2.30, 2.31):
  <https://zoek.officielebekendmakingen.nl/stb-2025-12.html>;
  consolidated text: <https://wetten.overheid.nl/BWBR0050714/2026-02-14>
- Energiebesluit, Stb. 2025, 347/348:
  <https://www.njb.nl/wetgeving/staatsbladen/energiebesluit/>
- Implementatiewet EMD-pakket, Kamerstuk 36990 (procedure and documents):
  <https://www.tweedekamer.nl/kamerstukken/wetsvoorstellen/detail?qry=wetsvoorstel%3A36990&cfg=wetsvoorsteldetails>
- RVO, energy communities:
  <https://www.rvo.nl/onderwerpen/samenwerken-energiegemeenschappen>
- Netbeheer Nederland, Energiewet FAQ (December 2025):
  <https://www.netbeheernederland.nl/sites/default/files/2025-12/faq_energiewet.pdf>
- Eerste Kamer, government letter on sharing and the EMD deadline:
  <https://eerstekamer.nl/9370000/1/j4nvi0xeni9vr2l_j9vvkyblr2b3ny8/vmniih4r5wvt/f=/vmnhigv01pzu.pdf>
- Overstappen.nl, 26 August 2026 (no supplier offers sharing):
  <https://www.overstappen.nl/nieuws/halfjaar-na-de-energiewet-geen-enkele-leverancier-biedt-consumenten-energie-delen-aan/>

The article numbers refer to the law as published in 2025. Check the
consolidated text for later amendments (for example, the end of net
metering, §4) before citing.

## 3. Collective generation (SCE subsidy)

Checked against RVO on 2026-11-27. The *Subsidieregeling Coöperatieve
Energieopwekking* (SCE) replaced the postcoderoos tax reduction in 2021.

| Rule | SCE (RVO) |
| --- | --- |
| Applicant | an energy cooperative or a homeowners' association (VvE) aimed at renewable generation |
| Technologies | solar PV and wind (hydropower no longer open) |
| Where members live | in the *postcoderoos*: the installation's four-digit postcode area plus the adjacent ones (VvE: at least 75 % of members) |
| Members' connections | small-consumer connections, at most 3x80 A in total |
| Minimum membership | one participating member per 5 kWp (solar) or 5 kW (wind) |
| Size, solar | 15-100 kWp on a small-consumer connection; 15 kWp-1 MWp and 1-6 MWp on a large-consumer connection |
| Subsidy | per kWh fed in, basisbedrag minus correctiebedrag, for 15 years (extension up to 1 year for small-consumer, 2 years for large-consumer connections); paid only with guarantees of origin |
| 2026 basisbedrag, solar | EUR 0.149/kWh (15-100 kWp, small-consumer connection), EUR 0.140/kWh (15 kWp-1 MWp, large-consumer) |
| Self-consumption | no subsidy for electricity the installation's own connection uses (small-consumer) |
| 2026 round | 2 March - 1 October 2026, budget EUR 78 M; closed |
| Next rounds | expected early 2027; budgets EUR 50 M (2027), 35 M (2028), 35 M (2029) |

**What it means for the model.** Members keep their own suppliers and
their own meters; they do not receive the cooperative's electricity. The
installation feeds into the grid, and the cooperative sells its output and
receives the subsidy, which it may pass on to members as a return. So,
unlike energy sharing (§2), the SCE route is an export from a community
asset (deck S4), and its value enters only the member view (§5), as a
transfer. It also uses the public grid, so the station limit (§6) applies.
Not run yet. The existing Thomassen rooftop installation in Loenen is
listed in `measures/community_assets.csv`.

Sources (accessed 2026-11-27):

- RVO, SCE: <https://www.rvo.nl/subsidies-financiering/sce>
- RVO, SCE conditions: <https://www.rvo.nl/subsidies-financiering/sce/voorwaarden>
- RVO, SCE solar PV categories and 2026 basisbedragen:
  <https://www.rvo.nl/subsidies-financiering/sce/zon-pv>

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

- Issue #5 is closed: SCE facts, Energiewet article numbers and the EMD
  bill status are verified above (2026-11-27). Re-check the EMD bill
  (Kamerstuk 36990) before citing its status.
- Member cost view: energy tax on shared kWh, 2027 tariffs, subsidies
  (issue #3).
- Repeat if the EMD implementation allows sharing with free choice of
  supplier: the model does not change, only the participation assumptions.
