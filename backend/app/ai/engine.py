"""Engine facade: wires dataset, knowledge base, rules, recommender, planner and search together."""
from __future__ import annotations

from functools import lru_cache

from ..config import load_config
from . import ml_affinity
from . import transport as trn
from . import accommodation as acc
from .budget import optimize, price_plan
from .data_loader import Dataset, load_dataset
from .knowledge_base import KnowledgeBase, build_kb
from .planner import PlanError, build_plan
from .recommendation import Recommender
from .replanning import apply_changes, edit_plan
from .rule_engine import RuleEngine
from .search import Graph, astar, bfs, build_network_graph, check_heuristic, dijkstra_cost
from ..schemas.prefs import Preferences


class Engine:
    def __init__(self, ds: Dataset | None = None, cfg: dict | None = None):
        self.cfg = cfg or load_config()
        self.ds = ds or load_dataset()
        self.kb: KnowledgeBase = build_kb(self.ds)
        self.rules = RuleEngine(self.cfg, self.kb)
        self.rec = Recommender(self.ds, self.kb, self.rules, self.cfg)
        self.graph: Graph = build_network_graph(self.ds)

    # ---- recommendation
    def recommend(self, prefs: Preferences, top_n: int = 10, sort: str = "match") -> dict:
        out = self.rec.recommend(prefs, top_n=top_n, sort=sort)
        for r in out["ranked"]:
            r["stravl_affinity"] = ml_affinity.affinity(r["id"], prefs)
        return out

    def compare(self, ids: list[str], prefs: Preferences) -> dict:
        rows, cols = [], []
        for did in ids:
            d = self.ds.destinations.get(did)
            if not d:
                continue
            ev = self.rec._evaluate(prefs, d) if prefs.origin in self.ds.origins else None
            elig = [a for a in self.ds.dest_attractions(did)]
            opts = trn.options(self.ds, prefs.origin, did, None, prefs.travellers) if prefs.origin in self.ds.origins else []
            cols.append(dict(
                id=did, name=d["name"], state=d["state"], match_score=(ev or {}).get("match_score"), excluded=(ev or {}).get("excluded_reasons"),
                estimated_cost=(ev or {}).get("cost", {}).get("typical"), cheapest_cost=(ev or {}).get("cost", {}).get("floor"),
                climate=d.get("climate"), best_seasons=d["best_seasons"], recommended_days=f"{d['min_days']}-{d['max_days']}",
                activities=d["tags"], accessibility=d.get("accessibility"), type=d["type"],
                transport=[f"{o['mode']} ~{o['one_way_hours']} h, INR {o['per_person_round_trip_inr']:,} pp return" for o in opts[:3]],
                pace_note=f"{len(elig)} attractions; average intensity {sum(a['intensity'] for a in elig) / max(len(elig), 1):.1f}/3"))
        return dict(destinations=cols, note="All costs are estimates from sample data.")

    def explain(self, dest_id: str, prefs: Preferences) -> dict:
        d = self.ds.destinations.get(dest_id)
        if not d:
            return dict(ok=False, error="Unknown destination")
        ev = self.rec._evaluate(prefs, d) if prefs.origin in self.ds.origins else None
        return dict(ok=True, destination=d["name"], evaluation=ev, facts=self.kb.facts_for_destination(dest_id),
                    stravl_affinity=ml_affinity.affinity(dest_id, prefs))

    # ---- planning
    def plan(self, prefs: Preferences, dest_id: str, **kw) -> dict:
        return build_plan(self.ds, self.cfg, self.kb, self.rules, prefs, dest_id, **kw)

    def optimize(self, plan: dict, relax: bool = False) -> dict:
        prefs = Preferences(**plan["prefs"])
        return optimize(self.ds, self.cfg, prefs, plan, allow_relax_preferences=relax)

    def replan(self, plan: dict, changes: dict) -> dict:
        return apply_changes(self.ds, self.cfg, self.kb, self.rules, plan, changes)

    def edit(self, plan: dict, op: dict) -> dict:
        return edit_plan(self.ds, self.cfg, plan, op)

    def reprice(self, plan: dict) -> dict:
        return price_plan(self.ds, self.cfg, Preferences(**plan["prefs"]), plan)

    def accommodation(self, plan_or_dest: str, travellers: int, nights: int, tier: str | None, accessibility: bool, planned: list[str] | None = None):
        return acc.options(self.ds, plan_or_dest, travellers, nights, tier, accessibility, planned)

    # ---- search demos
    def route_demo(self, start: str, goal: str, metric: str = "distance") -> dict:
        a = astar(self.graph, start, goal, metric)
        b = bfs(self.graph, start, goal)
        ref = dijkstra_cost(self.graph, start, goal, metric) if a["found"] else None
        nodes = [dict(id=n, label=self.graph.labels[n], lat=c[0], lon=c[1]) for n, c in self.graph.coords.items()]
        edges = [dict(a=u, b=v, km=round(e["km"], 1), hours=round(e["hours"], 2)) for u, v, e in self.graph.edges() if u < v]
        return dict(graph_kind=self.graph.kind, astar=a, bfs=b, dijkstra_reference=ref, heuristic_check=check_heuristic(self.graph, metric),
                    nodes=nodes, edges=edges, metric=metric)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return Engine()
