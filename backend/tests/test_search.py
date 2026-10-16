import itertools

import pytest

from app.ai.search import Graph, astar, bfs, build_network_graph, check_heuristic, dijkstra_cost


def toy_graph() -> Graph:
    """S -> G has a 1-hop direct edge that is a long detour; S-A-G is 2 hops but much cheaper."""
    g = Graph(kind="test")
    g.add_node("S", 20.0, 78.0, "Start"); g.add_node("A", 20.0, 79.0, "Mid"); g.add_node("G", 20.0, 80.0, "Goal"); g.add_node("X", 21.5, 79.0, "Detour")
    g.add_edge("S", "A", 110, 2.2); g.add_edge("A", "G", 110, 2.2)
    g.add_edge("S", "G", 500, 10.0)                 # direct but costly (>= straight-line 208 km)
    g.add_edge("S", "X", 240, 4.8); g.add_edge("X", "G", 240, 4.8)
    return g


def test_bfs_finds_fewest_hops_not_cheapest_route():
    """#5 BFS on an unweighted view returns the minimum number of edges, which is NOT the cheapest here."""
    g = toy_graph()
    b = bfs(g, "S", "G")
    assert b["found"] and b["path"] == ["S", "G"] and b["hops"] == 1
    assert b["total_km"] == 500 and "hops only" in b["note"]
    cheap = astar(g, "S", "G")
    assert cheap["path"] == ["S", "A", "G"] and cheap["total_km"] == 220 < b["total_km"]


def test_bfs_handles_unreachable_and_unknown_nodes():
    g = toy_graph(); g.add_node("Z", 25.0, 80.0, "Island")
    assert bfs(g, "S", "Z")["found"] is False
    assert bfs(g, "S", "nope")["found"] is False
    assert astar(g, "S", "Z")["found"] is False


def test_astar_optimal_with_consistent_heuristic():
    """#6 A* with a straight-line heuristic returns a minimum-cost path; the heuristic is verified consistent."""
    g = toy_graph()
    for metric in ("distance", "time"):
        assert check_heuristic(g, metric)["consistent"]
        r = astar(g, "S", "G", metric)
        assert r["found"] and r["path"] == ["S", "A", "G"] and r["optimal"]
        assert r["cost"] == pytest.approx(dijkstra_cost(g, "S", "G", metric), abs=0.01)
        assert r["expanded"] <= len(g.coords)
        assert all(abs(t["f"] - (t["g"] + t["h"])) < 0.11 for t in r["trace"])   # f = g + h in the trace


def test_astar_detects_inadmissible_graph():
    g = toy_graph(); g.add_edge("S", "A", 50, 1.0)   # 50 km < 104 km straight line: impossible, heuristic no longer consistent
    assert check_heuristic(g, "distance")["consistent"] is False


def test_astar_matches_dijkstra_on_modelled_network(ds):
    g = build_network_graph(ds)
    assert check_heuristic(g, "distance")["consistent"] and check_heuristic(g, "time")["consistent"]
    for s, t in itertools.permutations(list(g.coords), 2):
        for m in ("distance", "time"):
            assert astar(g, s, t, m)["cost"] == pytest.approx(dijkstra_cost(g, s, t, m), abs=0.01)


def test_network_graph_is_connected_and_labelled_as_modelled(ds):
    g = build_network_graph(ds)
    assert "modelled" in g.kind
    assert all(bfs(g, "orig", n)["found"] for n in g.coords)
