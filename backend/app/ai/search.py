"""Graph search: Breadth-First Search and A*.

Sample network (NOT real transport)
-----------------------------------
`build_network_graph` links every pair of places within `max_link_km` straight-line
distance (plus the minimum extra edges needed to keep the graph connected). An edge's
cost is `road_factor x straight-line distance` (road_factor >= 1), and its time is
cost / average speed. These links are MODELLED for demonstration; no real timetable or
route is implied.

A* definitions
--------------
State      : a place (node).          Action : travel along an edge.
g(n)       : accumulated edge cost (km, or hours for metric="time").
h(n)       : straight-line distance to the goal (km), or / v_max for time.
f(n)       : g(n) + h(n).
Because every edge cost >= straight-line distance between its endpoints (road_factor>=1),
h(u) <= c(u,v) + h(v) (triangle inequality) -> h is CONSISTENT, hence admissible, and A*
returns a minimum-cost path. `check_heuristic` verifies this edge by edge.

Complexity: BFS O(V+E). A* O(E log V) with a binary heap in the typical case; worst case
exponential in the solution depth for a poor heuristic.
"""
from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field

from .data_loader import Dataset
from .geo import haversine_km


@dataclass
class Graph:
    coords: dict[str, tuple[float, float]] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    adj: dict[str, dict[str, dict]] = field(default_factory=dict)
    kind: str = "sample network (modelled links - not real transport)"

    def add_node(self, nid: str, lat: float, lon: float, label: str | None = None) -> None:
        self.coords[nid] = (lat, lon); self.labels[nid] = label or nid; self.adj.setdefault(nid, {})

    def add_edge(self, u: str, v: str, km: float, hours: float, both: bool = True) -> None:
        self.adj[u][v] = dict(km=km, hours=hours)
        if both:
            self.adj[v][u] = dict(km=km, hours=hours)

    def edges(self):
        for u, nb in self.adj.items():
            for v, e in nb.items():
                yield u, v, e

    def v_max(self) -> float:
        return max((e["km"] / e["hours"] for _, _, e in self.edges() if e["hours"] > 0), default=1.0)

    def straight(self, a: str, b: str) -> float:
        return haversine_km(*self.coords[a], *self.coords[b])


def build_network_graph(ds: Dataset, max_link_km: float = 450.0, road_factor: float = 1.3, speed_kmph: float = 50.0) -> Graph:
    g = Graph()
    for o in ds.origins.values():
        g.add_node(o["id"], o["lat"], o["lon"], o["name"])
    for d in ds.destinations.values():
        g.add_node(d["id"], d["lat"], d["lon"], d["name"])
    ids = list(g.coords)
    pairs = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            pairs.append((g.straight(a, b), a, b))
    pairs.sort()
    parent = {n: n for n in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    for s, a, b in pairs:
        if s <= max_link_km:
            km = s * road_factor
            g.add_edge(a, b, km, km / speed_kmph)
            parent[find(a)] = find(b)
    for s, a, b in pairs:  # Kruskal-style: join remaining components with the cheapest links
        if find(a) != find(b):
            km = s * road_factor
            g.add_edge(a, b, km, km / speed_kmph)
            parent[find(a)] = find(b)
    return g


# ------------------------------------------------------------------ BFS
def bfs(graph: Graph, start: str, goal: str) -> dict:
    """Fewest-edges path; every edge is treated as equal. Not necessarily cheapest or fastest."""
    if start not in graph.adj or goal not in graph.adj:
        return dict(found=False, path=[], hops=None, explored=[], reason="unknown node")
    q, prev, seen, order = deque([start]), {start: None}, {start}, []
    while q:
        u = q.popleft(); order.append(u)
        if u == goal:
            break
        for v in sorted(graph.adj[u]):  # sorted -> deterministic
            if v not in seen:
                seen.add(v); prev[v] = u; q.append(v)
    if goal not in prev:
        return dict(found=False, path=[], hops=None, explored=order, reason="no route in graph")
    path, n = [], goal
    while n is not None:
        path.append(n); n = prev[n]
    path.reverse()
    km = sum(graph.adj[a][b]["km"] for a, b in zip(path, path[1:]))
    hrs = sum(graph.adj[a][b]["hours"] for a, b in zip(path, path[1:]))
    return dict(found=True, path=path, hops=len(path) - 1, explored=order, total_km=round(km, 1), total_hours=round(hrs, 2),
                note="BFS minimises the number of hops only; cost and time are reported for comparison with A*.")


# ------------------------------------------------------------------ A*
def _h(graph: Graph, n: str, goal: str, metric: str, vmax: float) -> float:
    d = graph.straight(n, goal)
    return d if metric == "distance" else d / vmax


def astar(graph: Graph, start: str, goal: str, metric: str = "distance", trace_limit: int = 40) -> dict:
    if metric not in ("distance", "time"):
        raise ValueError("metric must be 'distance' or 'time'")
    if start not in graph.adj or goal not in graph.adj:
        return dict(found=False, path=[], cost=None, trace=[], reason="unknown node")
    key = "km" if metric == "distance" else "hours"
    vmax = graph.v_max()
    g_best = {start: 0.0}
    prev: dict[str, str | None] = {start: None}
    h0 = _h(graph, start, goal, metric, vmax)
    open_heap = [(h0, h0, 0.0, start)]  # (f, h, g, node): ties -> smaller h, then name
    trace, expanded, generated = [], 0, 1
    done: dict[str, float] = {}         # node -> g at which it was expanded
    while open_heap:
        f, h, g, u = heapq.heappop(open_heap)
        if g > g_best[u] + 1e-12:
            continue                     # stale: a cheaper path to u was found after this was queued
        if u in done and done[u] <= g + 1e-12:
            continue                     # already expanded at an equal or better cost
        done[u] = g; expanded += 1
        if len(trace) < trace_limit:
            frontier = sorted((round(ff, 1), n) for ff, _h_, gg, n in open_heap if gg <= g_best[n] + 1e-12)[:5]
            trace.append(dict(step=expanded, node=u, label=graph.labels[u], g=round(g, 1), h=round(h, 1), f=round(f, 1),
                              frontier=[dict(node=n, f=ff) for ff, n in frontier]))
        if u == goal:
            path, n = [], goal
            while n is not None:
                path.append(n); n = prev[n]
            path.reverse()
            km = sum(graph.adj[a][b]["km"] for a, b in zip(path, path[1:]))
            hrs = sum(graph.adj[a][b]["hours"] for a, b in zip(path, path[1:]))
            return dict(found=True, path=path, labels=[graph.labels[p] for p in path], metric=metric, cost=round(g, 2),
                        total_km=round(km, 1), total_hours=round(hrs, 2), expanded=expanded, generated=generated, trace=trace,
                        optimal=True, note="Heuristic is consistent (checked), so the path is minimum-cost for this metric on this modelled graph.")
        for v in sorted(graph.adj[u]):
            ng = g + graph.adj[u][v][key]
            if ng + 1e-12 < g_best.get(v, float("inf")):
                g_best[v] = ng; prev[v] = u; generated += 1
                hv = _h(graph, v, goal, metric, vmax)
                heapq.heappush(open_heap, (ng + hv, hv, ng, v))
    return dict(found=False, path=[], cost=None, expanded=expanded, generated=generated, trace=trace, reason="no route in graph")


def check_heuristic(graph: Graph, metric: str = "distance") -> dict:
    """Verify consistency h(u) <= c(u,v) + h(v) for every edge and every possible goal."""
    key = "km" if metric == "distance" else "hours"
    vmax = graph.v_max()
    worst, violations = 0.0, 0
    for goal in graph.coords:
        for u, v, e in graph.edges():
            slack = _h(graph, u, goal, metric, vmax) - (e[key] + _h(graph, v, goal, metric, vmax))
            worst = max(worst, slack)
            if slack > 1e-9:
                violations += 1
    return dict(metric=metric, consistent=violations == 0, violations=violations, max_slack=round(worst, 6))


def dijkstra_cost(graph: Graph, start: str, goal: str, metric: str = "distance") -> float | None:
    """Reference implementation (h = 0) used by tests to confirm A* optimality."""
    key = "km" if metric == "distance" else "hours"
    dist = {start: 0.0}; pq = [(0.0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18):
            continue
        if u == goal:
            return d
        for v, e in graph.adj[u].items():
            nd = d + e[key]
            if nd < dist.get(v, 1e18):
                dist[v] = nd; heapq.heappush(pq, (nd, v))
    return None
