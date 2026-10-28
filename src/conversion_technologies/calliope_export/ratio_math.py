"""Calliope "additional math" fixing the multi-carrier ratio gap in ``modern``.

Calliope's own base ``balance_conversion`` constraint is
``sum(flow_out_inc_eff, over=carriers) == sum(flow_in_inc_eff, over=carriers)``
-- a sum across carriers, not a per-carrier equation. For a technology with
more than one carrier on one side (heat pump: 2 input carriers; combined
heat and power: 2 output carriers), setting a real per-carrier efficiency on
every carrier of that side (what ``modern.py`` already does, via
``flow_in_eff``/``flow_out_eff`` with ``dims: carriers``) does not, by
itself, pin how that side's total splits between its carriers -- worked
through with actual numbers in ``docs/calliope_schema_mapping.md``, it makes
the base balance double-count fuel input for CHP and makes the intended
heat-pump dispatch fail to satisfy the balance equation at all.

This module generates the same fix Calliope's own team uses in their
reference CHP example (``calliope/src/calliope/example_models/urban_scale/
additional_math.yaml``: a ``link_chp_outputs``-style equality constraint
plus a scoped ``balance_conversion`` override) -- generalised so it is
driven structurally (does this tech have >1 carrier on a side?) rather than
by technology name, and symmetric for the input side (heat pump) as well as
the output side (CHP). Boiler (1 carrier each side) triggers none of this;
its balance is already just that one carrier.

Not validated against a running Calliope install (none is available here) --
the fix was derived algebraically from Calliope's own published base math
and cross-checked against its official example, not from a real solve. See
``docs/calliope_schema_mapping.md`` "Carrier ratio math" for the full
derivation and that caveat.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from conversion_technologies.core.technology import TechnologySpec
from conversion_technologies.core.validation import require_range

_LINK_IN = "link_flow_in_carriers"
_LINK_OUT = "link_flow_out_carriers"
_BALANCE_OVERRIDE = "balance_conversion"


def _secondary_carriers(
    carriers: dict[str, float], primary: str | None, *, tech_id: str, side: str
) -> list[str]:
    """Every carrier in ``carriers`` other than ``primary``.

    Raises if there's more than one -- this module only knows how to tie a
    *single* secondary carrier to the primary per side (true of every
    technology this package defines today); raising rather than silently
    dropping data keeps a future 3-carrier technology from getting
    subtly-wrong generated math.
    """
    others = [c for c in carriers if c != primary]
    if not others:
        return others
    if primary is None:
        raise ValueError(
            f"Technology '{tech_id}' has {len(carriers)} carriers on its "
            f"{side} side but no primary_carrier_{side} set -- ratio_math "
            "needs one to know which carrier every other one is tied to."
        )
    if len(others) > 1:
        raise ValueError(
            f"Technology '{tech_id}' has {len(others)} secondary carriers "
            f"on its {side} side ({sorted(others)}); ratio_math only "
            "supports a single secondary carrier per side today."
        )
    return others


def _ratio(
    carriers: dict[str, float], primary: str, secondary: str, *, tech_id: str, side: str
) -> float:
    primary_value = carriers[primary]
    if primary_value == 0:
        raise ValueError(
            f"Technology '{tech_id}': primary_carrier_{side} '{primary}' has "
            f"a zero flow ratio -- cannot compute a carrier_flow_ratio_{side} "
            "from it."
        )
    return require_range(
        carriers[secondary] / primary_value,
        0,
        float("inf"),
        name=f"carrier_flow_ratio_{side}[{secondary}]",
        tech_id=tech_id,
        inclusive_lo=False,
        inclusive_hi=False,
    )


def carrier_flow_ratios(tech: TechnologySpec) -> dict[str, float]:
    """``{"carrier_flow_ratio_in": ...}``/``{"carrier_flow_ratio_out": ...}``
    for ``tech`` -- empty if it has one carrier on each side (e.g. boiler).

    The actual per-tech *value* -- confirmed against a real
    ``calliope==0.7.0`` install, not assumed: Calliope 0.7.0's math-file
    ``parameters:`` schema only accepts metadata (``default``/``title``/
    ``description``), not an indexed ``data``/``index``/``dims`` block, so
    the value itself has to live on each tech's own body in the model
    definition (``modern.py`` calls this and merges the result in) rather
    than inside ``additional_math.yaml``'s ``parameters`` block, which
    only ever declares the parameter's existence/metadata now.
    """
    result: dict[str, float] = {}
    secondary_in = _secondary_carriers(
        tech.carriers_in, tech.primary_carrier_in, tech_id=tech.id, side="in"
    )
    if secondary_in:
        assert tech.primary_carrier_in is not None
        result["carrier_flow_ratio_in"] = _ratio(
            tech.carriers_in, tech.primary_carrier_in, secondary_in[0], tech_id=tech.id, side="in"
        )
    secondary_out = _secondary_carriers(
        tech.carriers_out, tech.primary_carrier_out, tech_id=tech.id, side="out"
    )
    if secondary_out:
        assert tech.primary_carrier_out is not None
        result["carrier_flow_ratio_out"] = _ratio(
            tech.carriers_out, tech.primary_carrier_out, secondary_out[0], tech_id=tech.id, side="out"
        )
    return result


def build_ratio_math(techs: Iterable[TechnologySpec]) -> dict[str, Any] | None:
    """Calliope "additional math" (``parameters`` + ``constraints``) so a
    solve respects the fixed carrier ratio on every technology in ``techs``
    that has more than one carrier on one side.

    Returns ``None`` if no technology in ``techs`` needs it (e.g. an
    all-boiler export) -- callers should skip writing a file in that case
    rather than emit an empty one.
    """
    link_in_equations: list[dict[str, str]] = []
    link_out_equations: list[dict[str, str]] = []
    balance_equations: list[dict[str, str]] = []
    techs_with_ratio_in: set[str] = set()
    techs_with_ratio_out: set[str] = set()

    for tech in techs:
        secondary_in = _secondary_carriers(
            tech.carriers_in, tech.primary_carrier_in, tech_id=tech.id, side="in"
        )
        secondary_out = _secondary_carriers(
            tech.carriers_out, tech.primary_carrier_out, tech_id=tech.id, side="out"
        )
        if not secondary_in and not secondary_out:
            continue  # single carrier each side (e.g. boiler) -- untouched

        if secondary_in:
            carrier = secondary_in[0]
            techs_with_ratio_in.add(tech.id)
            link_in_equations.append(
                {
                    "where": f"[{tech.id}] in techs",
                    "expression": (
                        f"flow_in[carriers={carrier}] == "
                        f"flow_in[carriers={tech.primary_carrier_in}] * carrier_flow_ratio_in"
                    ),
                }
            )

        if secondary_out:
            carrier = secondary_out[0]
            techs_with_ratio_out.add(tech.id)
            link_out_equations.append(
                {
                    "where": f"[{tech.id}] in techs",
                    "expression": (
                        f"flow_out[carriers={carrier}] == "
                        f"flow_out[carriers={tech.primary_carrier_out}] * carrier_flow_ratio_out"
                    ),
                }
            )

        balance_equations.append(
            {
                "where": f"[{tech.id}] in techs",
                "expression": (
                    f"flow_out_inc_eff[carriers={tech.primary_carrier_out}] == "
                    f"flow_in_inc_eff[carriers={tech.primary_carrier_in}]"
                ),
            }
        )

    if not balance_equations:
        return None

    parameters: dict[str, Any] = {}
    constraints: dict[str, Any] = {}

    if techs_with_ratio_in:
        # Metadata only -- confirmed against calliope==0.7.0, the real
        # math-file `parameters:` schema has no room for indexed data
        # (`data`/`index`/`dims`, used at model-definition level only).
        # Each affected tech's actual value is set directly on its own
        # body instead, via modern.py calling carrier_flow_ratios().
        parameters["carrier_flow_ratio_in"] = {
            "description": (
                "Fixed ratio of a technology's secondary input carrier flow "
                "to its primary input carrier flow (e.g. a heat pump's free "
                "heat source relative to its electricity draw)."
            ),
            "default": 1,
        }
        constraints[_LINK_IN] = {
            "description": (
                "Ties each technology's secondary input carrier to its "
                "primary input carrier via carrier_flow_ratio_in."
            ),
            "foreach": ["nodes", "techs", "timesteps"],
            # Restricting the tech dimension by explicit membership (not just
            # the "carrier_flow_ratio_in" parameter-exists check) lets
            # Calliope prune these techs before building the dense
            # nodes x techs x timesteps array -- at 1,260-node scale,
            # evaluating every equation branch against *all* techs first
            # (see docs/calliope_schema_mapping.md "Carrier ratio math")
            # caused an ArrayMemoryError on a 607M-element array.
            "where": (
                f"carrier_flow_ratio_in AND [{', '.join(sorted(techs_with_ratio_in))}] in techs"
            ),
            "equations": link_in_equations,
        }

    if techs_with_ratio_out:
        parameters["carrier_flow_ratio_out"] = {
            "description": (
                "Fixed ratio of a technology's secondary output carrier flow "
                "to its primary output carrier flow (e.g. CHP heat relative "
                "to its electricity output)."
            ),
            "default": 1,
        }
        constraints[_LINK_OUT] = {
            "description": (
                "Ties each technology's secondary output carrier to its "
                "primary output carrier via carrier_flow_ratio_out."
            ),
            "foreach": ["nodes", "techs", "timesteps"],
            "where": (
                f"carrier_flow_ratio_out AND [{', '.join(sorted(techs_with_ratio_out))}] in techs"
            ),
            "equations": link_out_equations,
        }

    balance_techs = techs_with_ratio_in | techs_with_ratio_out
    constraints[_BALANCE_OVERRIDE] = {
        "description": (
            "Overrides the base balance_conversion for technologies with "
            "more than one carrier on one side: restricts the balance to "
            "each side's primary carrier only, since link_flow_in_carriers/"
            "link_flow_out_carriers ties every secondary carrier to that "
            "primary separately. Without this override the base (summed) "
            "balance double-counts input for a technology with a real "
            "efficiency set on more than one carrier of the same side -- "
            "see docs/calliope_schema_mapping.md. Absent for boiler and any "
            "other single-carrier-per-side technology, which keep the "
            "unmodified base balance_conversion."
        ),
        "foreach": ["nodes", "techs", "timesteps"],
        # Explicit [tech, ...] in techs membership (not just
        # base_tech==conversion, which still matches every conversion tech
        # in the model) keeps Calliope from building a dense
        # nodes x all-techs x timesteps array -- see the matching note on
        # link_flow_in_carriers above.
        "where": (
            "base_tech==conversion AND NOT include_storage==true AND "
            f"[{', '.join(sorted(balance_techs))}] in techs"
        ),
        "equations": balance_equations,
    }

    return {"parameters": parameters, "constraints": constraints}
