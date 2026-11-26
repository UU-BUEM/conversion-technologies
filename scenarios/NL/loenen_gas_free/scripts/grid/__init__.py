"""Grid model for the energy-community workflow (step 1).

Three sources, tried in this order by ``build_grid.py --source auto``:

1. ``provided``: a network the user supplies (``provided.py``);
2. ``dso``: the distribution system operator's open data, Liander for
   Loenen (``liander.py``);
3. ``pylovo``: a synthetic low-voltage grid from enerplanet-pylovo's API
   (``pylovo.py``).

Every source writes the same grid package (``common.py``), so later steps
never need to know where the grid came from. See
``docs/phase7_grid.md``.
"""
