"""Assign buildings to MV/LV stations along low-voltage cable geometry.

Used when a source gives cable *routes* but no electrical topology, which
is what Liander's open data is (geometry only: no cable types, no switch
states, no connectivity table).

Method (each step is an assumption, listed in the manifest):

1. **Graph from geometry.** Every cable is a chain of vertices. A cable's
   end vertex is joined to any vertex of another cable within ``snap_m``
   (GIS cable segments meet at joints, not always at exactly the same
   coordinate). Interior vertices of different cables are never joined, so
   cables that merely cross or run side by side stay separate.
2. **Stations.** A station is attached to every cable *end* within
   ``station_radius_m`` (LV feeders end at the station); if none, to the
   nearest cable within twice that radius.
3. **Buildings.** A building connects at the nearest point of the nearest
   cable within ``max_connection_m`` of its footprint centroid (service
   cables are not in the data).
4. **Station per building.** Multi-source shortest path along the cables:
   each building goes to the station with the shortest cable route. Real
   LV networks are radial with normally-open points in street cabinets,
   which the data does not show; the shortest-route split stands in for
   them.
5. **Feeder.** The first cable leaving the station on the building's
   route.

Buildings with no cable within reach, or on a cable piece that reaches no
station, fall back to the nearest station in a straight line
(``euclidean_fallback``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from grid.common import line_feature, nearest_station


@dataclass
class TraceSettings:
    snap_m: float = 1.0
    station_radius_m: float = 30.0
    max_connection_m: float = 75.0
    index_step_m: float = 10.0

    def describe(self) -> list[str]:
        return [
            f"Cable ends join other cables' vertices within {self.snap_m} m; "
            "interior vertices of different cables are never joined.",
            f"A station connects to every cable end within {self.station_radius_m} m "
            f"(else the nearest cable within {2 * self.station_radius_m} m).",
            f"A building connects to the nearest cable within {self.max_connection_m} m of its "
            "centroid (service cables are not in the data).",
            "Each building goes to the station with the shortest cable route; this stands in "
            "for the normally-open points the data does not show.",
            "Feeder = first cable leaving the station on that route.",
        ]


class CableGraph:
    def __init__(self, lines: list[np.ndarray], snap_m: float) -> None:
        self.lines = [np.asarray(line, dtype=float) for line in lines if len(line) >= 2]
        xy = np.vstack(self.lines)
        starts = np.cumsum([0] + [len(line) for line in self.lines[:-1]])
        ends = starts + np.array([len(line) for line in self.lines]) - 1
        endpoint_idx = np.concatenate([starts, ends])

        # Join each cable end with every vertex within snap_m.
        tree = cKDTree(xy)
        rows, cols = [], []
        for i, neighbours in zip(
            endpoint_idx, tree.query_ball_point(xy[endpoint_idx], snap_m), strict=True
        ):
            rows.extend([i] * len(neighbours))
            cols.extend(neighbours)
        n = len(xy)
        adjacency = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
        _, label = connected_components(adjacency, directed=False)
        _, first = np.unique(label, return_index=True)
        self.node_xy = xy[first]  # node id == label
        self.vertex_node = label
        self.is_end = np.zeros(len(self.node_xy), dtype=bool)
        self.is_end[label[endpoint_idx]] = True

        self.graph = nx.Graph()
        self.line_nodes: list[np.ndarray] = []
        for k, (s, line) in enumerate(zip(starts, self.lines, strict=True)):
            nodes = label[s : s + len(line)]
            self.line_nodes.append(nodes)
            for a, b in zip(nodes[:-1], nodes[1:], strict=True):
                if a == b:
                    continue
                w = float(np.hypot(*(self.node_xy[a] - self.node_xy[b])))
                if not self.graph.has_edge(a, b) or self.graph[a][b]["weight"] > w:
                    self.graph.add_edge(int(a), int(b), weight=w, line=k)

        # Segment index for "nearest point on a cable" queries.
        edges = np.array([(u, v) for u, v in self.graph.edges()], dtype=int).reshape(
            -1, 2
        )
        self.seg_u, self.seg_v = edges[:, 0], edges[:, 1]
        self._p = self.node_xy[self.seg_u]
        self._q = self.node_xy[self.seg_v]
        self._len = np.hypot(*(self._q - self._p).T)

    def build_index(self, step_m: float) -> None:
        samples, owner = [], []
        for i, (p, q, length) in enumerate(
            zip(self._p, self._q, self._len, strict=True)
        ):
            n = max(1, int(np.ceil(length / step_m)))
            t = np.linspace(0.0, 1.0, n + 1)
            samples.append(p + np.outer(t, q - p))
            owner.append(np.full(n + 1, i))
        self._sample_tree = cKDTree(np.vstack(samples))
        self._sample_owner = np.concatenate(owner)
        self._step = step_m

    def nearest_segment(
        self, point: np.ndarray, max_dist: float
    ) -> tuple[int, float, float] | None:
        """(segment index, position t along it, distance) of the nearest
        cable within ``max_dist``, or ``None``."""
        hits = self._sample_tree.query_ball_point(point, max_dist + self._step)
        if not hits:
            return None
        best: tuple[int, float, float] | None = None
        for seg in np.unique(self._sample_owner[hits]):
            p, d, length = self._p[seg], self._q[seg] - self._p[seg], self._len[seg]
            t = (
                0.0
                if length == 0
                else float(np.clip(np.dot(point - p, d) / length**2, 0, 1))
            )
            dist = float(np.hypot(*(p + t * d - point)))
            if dist <= max_dist and (best is None or dist < best[2]):
                best = (int(seg), t, dist)
        return best


def trace(
    cables_rd: list[np.ndarray],
    stations: pd.DataFrame,
    buildings: pd.DataFrame,
    settings: TraceSettings,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    """Assign ``buildings`` (columns ``x``, ``y``, ids) to ``stations``
    (columns ``trafo_id``, ``x``, ``y``) along ``cables_rd``.

    Returns the building map (``trafo_id``, ``feeder_id``,
    ``network_distance_m``, ``connection_distance_m``, ``method``), the
    cables as GeoJSON features with their station and feeder, and stats.
    """
    cg = CableGraph(cables_rd, settings.snap_m)
    cg.build_index(settings.index_step_m)
    g = cg.graph.copy()

    end_nodes = np.flatnonzero(cg.is_end)
    end_tree = cKDTree(cg.node_xy[end_nodes])
    sources = []
    unattached = []
    for _, st in stations.iterrows():
        s_node = ("S", st["trafo_id"])
        point = np.array([st["x"], st["y"]])
        near = end_tree.query_ball_point(point, settings.station_radius_m)
        links = [
            (int(end_nodes[i]), float(np.hypot(*(cg.node_xy[end_nodes[i]] - point))))
            for i in near
        ]
        if not links:
            hit = cg.nearest_segment(point, 2 * settings.station_radius_m)
            if hit is not None:
                seg, t, _ = hit
                length = cg._len[seg]
                links = [
                    (int(cg.seg_u[seg]), t * length),
                    (int(cg.seg_v[seg]), (1 - t) * length),
                ]
        if not links:
            unattached.append(st["trafo_id"])
            continue
        for node, w in links:
            g.add_edge(s_node, node, weight=w)
        sources.append(s_node)

    dist, paths = nx.multi_source_dijkstra(g, sources) if sources else ({}, {})

    feeder_keys: dict[Any, tuple[int, int | None]] = {}
    for node, path in paths.items():
        if isinstance(node, tuple):
            continue
        feeder_keys[node] = (path[1], path[2] if len(path) > 2 else None)
    feeder_names: dict[tuple[Any, tuple[int, int | None]], str] = {}
    per_trafo: dict[Any, list[tuple[int, int | None]]] = {}
    for node, key in feeder_keys.items():
        per_trafo.setdefault(paths[node][0][1], []).append(key)
    for trafo, keys in per_trafo.items():
        full = sorted({k for k in keys if k[1] is not None})
        for i, k in enumerate(full, start=1):
            feeder_names[(trafo, k)] = f"{trafo}-F{i:02d}"

    def node_assignment(node: int) -> tuple[Any, str | None] | None:
        if node not in paths:
            return None
        trafo = paths[node][0][1]
        return trafo, feeder_names.get((trafo, feeder_keys[node]))

    stations_xy = stations[["x", "y"]].to_numpy()
    rows = []
    for _, b in buildings.iterrows():
        point = np.array([b["x"], b["y"]])
        row = {
            "building_feature_id": b["building_feature_id"],
            "trafo_id": None,
            "feeder_id": None,
            "network_distance_m": None,
            "connection_distance_m": None,
            "method": "euclidean_fallback",
        }
        hit = cg.nearest_segment(point, settings.max_connection_m)
        if hit is not None:
            seg, t, conn = hit
            length = cg._len[seg]
            u, v = int(cg.seg_u[seg]), int(cg.seg_v[seg])
            options = [
                (dist[n] + off, n)
                for n, off in ((u, t * length), (v, (1 - t) * length))
                if n in dist
            ]
            if options:
                d_net, node = min(options)
                trafo, feeder = node_assignment(node)  # type: ignore[misc]
                if feeder is None:  # the station-side end; take the other end's feeder
                    other = v if node == u else u
                    alt = node_assignment(other)
                    if alt is not None and alt[0] == trafo:
                        feeder = alt[1]
                row.update(
                    trafo_id=trafo,
                    feeder_id=feeder,
                    network_distance_m=round(float(d_net), 1),
                    connection_distance_m=round(conn, 1),
                    method="lv_network",
                )
            else:
                row["connection_distance_m"] = round(conn, 1)
        if row["method"] == "euclidean_fallback":
            idx, _ = nearest_station(point[None, :], stations_xy)
            row["trafo_id"] = stations["trafo_id"].iloc[int(idx[0])]
        rows.append(row)
    building_map = pd.DataFrame(rows)

    features = []
    for k, (line, nodes) in enumerate(zip(cg.lines, cg.line_nodes, strict=True)):
        assigned = [
            a for a in (node_assignment(int(n)) for n in nodes) if a is not None
        ]
        trafo = feeder = None
        if assigned:
            trafo = pd.Series([a[0] for a in assigned]).mode().iloc[0]
            feeders = [a[1] for a in assigned if a[0] == trafo and a[1] is not None]
            feeder = pd.Series(feeders).mode().iloc[0] if feeders else None
        features.append(
            line_feature(
                line,
                {
                    "line_id": k,
                    "trafo_id": trafo,
                    "feeder_id": feeder,
                    "cable_type": None,
                },
            )
        )

    # Agreement with a plain nearest-station assignment, as a sanity figure.
    idx, _ = nearest_station(buildings[["x", "y"]].to_numpy(), stations_xy)
    nearest = stations["trafo_id"].to_numpy()[idx]
    on_network = building_map["method"] == "lv_network"
    agree = float(
        (
            building_map.loc[on_network, "trafo_id"].to_numpy() == nearest[on_network]
        ).mean()
    )
    stats = {
        "cable_graph": {
            "n_cables": len(cg.lines),
            "n_nodes": cg.graph.number_of_nodes(),
            "n_edges": cg.graph.number_of_edges(),
            "n_connected_pieces": nx.number_connected_components(cg.graph),
        },
        "stations_not_on_any_cable": unattached,
        "share_same_station_as_straight_line_nearest": round(agree, 3)
        if on_network.any()
        else None,
    }
    return building_map, features, stats
