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
