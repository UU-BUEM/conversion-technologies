"""Carrier name constants shared across technology definitions.

Centralised so exporters and technology modules refer to the same strings
instead of scattering carrier-name literals through the codebase.
"""

from __future__ import annotations

ELECTRICITY = "electricity"
NATURAL_GAS = "natural_gas"
HYDROGEN = "hydrogen"
BIOMASS = "biomass"
HEAT = "heat"
AMBIENT_HEAT = "ambient_heat"
GROUND_HEAT = "ground_heat"
COOLING = "cooling"
# Energy inside an electric vehicle's battery system (DC side of the
# charger). Separate from ELECTRICITY so the car's battery, its charger and
# its driving demand form their own balance at each node: the battery can
# only be filled through a charger, and only while the car is connected.
EV_ELECTRICITY = "ev_electricity"
