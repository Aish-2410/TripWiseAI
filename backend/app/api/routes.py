"""HTTP API."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, Query

from ..ai import chat as chat_mod
from ..ai import llm, ml_affinity
from ..ai.data_loader import CLIMATES, INTERESTS, SEASONS, TIERS
from ..ai.engine import get_engine
from ..ai.planner import PlanError
from ..config import APP_DATA, DEFAULT_CONFIG
from ..schemas import api as S
from ..schemas.prefs import ItineraryRequest, Preferences, RecommendRequest
from ..services.storage import Storage
from ..config import DB_PATH

router = APIRouter(prefix="/api")
_store: Storage | None = None


def store() -> Storage:
    global _store
    if _store is None:
        _store = Storage(DB_PATH)
    return _store


def _plan_err(e: Exception):
    raise HTTPException(status_code=400, detail=str(e))


@router.get("/health")
def health():
    return dict(status="ok")


@router.get("/meta")
def meta():
    e = get_engine()
    return dict(dataset=e.ds.meta, counts=dict(destinations=len(e.ds.destinations), attractions=len(e.ds.attractions), accommodation=len(e.ds.accommodation),
                                               transport_links=len(e.ds.transport), origins=len(e.ds.origins)),
                data_issues=e.ds.issues, kb=e.kb.stats(), ml=dict(available=ml_affinity.metrics() is not None),
                chat=dict(understanding=("gemini+rules" if llm.enabled() else "rules"), llm_enabled=llm.enabled(), model=(llm.model_name() if llm.enabled() else None)),
                options=dict(interests=INTERESTS, climates=CLIMATES, seasons=SEASONS, tiers=TIERS, modes=["bus", "train", "car", "flight"]),
                origins=[dict(id=o["id"], name=o["name"]) for o in e.ds.origins.values()],
                sources=[dict(name="Stravl-Data", url="https://github.com/Stravl/Stravl-Data", use="optional ML component (preference learning)", status="integrated"),
                         dict(name="TripWise sample dataset", url=None, use="destinations, attractions, stays, transport model", status="integrated (illustrative sample)"),
                         dict(name="Wikivoyage, Kaggle, Open Travel Data, Hugging Face", url=None, use="not integrated", status="not reachable from the build environment or declined")])


@router.get("/destinations")
def destinations():
    e = get_engine()
    return [dict(id=d["id"], name=d["name"], state=d["state"], region=d["region"], type=d["type"], climate=d.get("climate"), tags=d["tags"], wiki=d.get("wiki"),
                 min_days=d["min_days"], max_days=d["max_days"], description=d["description"], lat=d["lat"], lon=d["lon"], accessibility=d.get("accessibility"),
                 best_seasons=d["best_seasons"], is_sample=True) for d in sorted(e.ds.destinations.values(), key=lambda x: x["name"])]


@router.get("/destinations/{did}")
def destination(did: str):
    e = get_engine()
    d = e.ds.destinations.get(did)
    if not d:
        raise HTTPException(404, "Unknown destination")
    return dict(destination=d, attractions=sorted(e.ds.dest_attractions(did), key=lambda a: (-a["significance"], a["name"])), accommodation=e.ds.dest_stays(did),
                facts=e.kb.facts_for_destination(did))


@router.post("/recommend")
def recommend(req: RecommendRequest):
    return get_engine().recommend(req.prefs, req.top_n, req.sort)


@router.post("/compare")
def compare(req: S.CompareRequest):
    return get_engine().compare(req.ids, req.prefs)


@router.post("/explain")
def explain(req: S.ExplainRequest):
    r = get_engine().explain(req.destination_id, req.prefs)
    if not r.get("ok"):
        raise HTTPException(404, r.get("error", "Unknown destination"))
    return r


@router.post("/plan")
def plan(req: ItineraryRequest):
    try:
        p = get_engine().plan(req.prefs, req.destination_id, transport_mode=req.transport_mode, tier=req.accommodation_tier, food_tier=req.food_tier)
    except PlanError as e:
        _plan_err(e)
    p["version"] = 1
    return p


@router.post("/plan/edit")
def plan_edit(req: S.EditRequest):
    r = get_engine().edit(req.plan, req.op)
    if not r["ok"]:
        raise HTTPException(400, r["error"])
    return r


@router.post("/plan/optimize")
def plan_optimize(req: S.OptimizeRequest):
    return get_engine().optimize(req.plan, req.relax)


@router.post("/plan/replan")
def plan_replan(req: S.ReplanRequest):
    r = get_engine().replan(req.plan, req.changes)
    if not r["ok"]:
        raise HTTPException(400, r["error"])
    return r


@router.post("/plan/reprice")
def plan_reprice(req: S.PlanOnly):
    return get_engine().reprice(req.plan)


@router.post("/accommodation")
def accommodation(req: S.AccommodationRequest):
    e = get_engine()
    if req.destination_id not in e.ds.destinations:
        raise HTTPException(404, "Unknown destination")
    return e.accommodation(req.destination_id, req.travellers, req.nights, req.tier, req.accessibility_required, req.planned_attraction_ids or None)


@router.get("/transport")
def transport(origin: str, destination: str, travellers: int = Query(1, ge=1, le=12), days: int | None = None):
    from ..ai import transport as trn
    e = get_engine()
    if origin not in e.ds.origins or destination not in e.ds.destinations:
        raise HTTPException(404, "Unknown origin or destination")
    return trn.options(e.ds, origin, destination, None, travellers, False, days)


# ---------------------------------------------------------------- config
@router.get("/config")
def get_config():
    e = get_engine()
    return dict(weights=e.cfg["weights"], weight_docs=e.cfg["weight_docs"], defaults=DEFAULT_CONFIG["weights"], pace=e.cfg["pace"],
                limited_budget_per_person_day=e.cfg["limited_budget_per_person_day"], beam_width=e.cfg["beam_width"])


@router.put("/config/weights")
def set_weights(req: S.WeightsUpdate):
    e = get_engine()
    keys = set(DEFAULT_CONFIG["weights"])
    if set(req.weights) != keys or any(v < 0 for v in req.weights.values()) or sum(req.weights.values()) <= 0:
        raise HTTPException(400, f"Provide non-negative weights for exactly: {sorted(keys)} with a positive sum.")
    tot = sum(req.weights.values())
    e.cfg["weights"] = {k: round(v / tot, 4) for k, v in req.weights.items()}
    (APP_DATA / "config.json").write_text(json.dumps(dict(weights=e.cfg["weights"]), indent=1))
    return dict(weights=e.cfg["weights"], note="Weights were normalised to sum to 1.")


@router.delete("/config/weights")
def reset_weights():
    e = get_engine()
    e.cfg["weights"] = dict(DEFAULT_CONFIG["weights"])
    p = APP_DATA / "config.json"
    if p.exists():
        p.unlink()
    return dict(weights=e.cfg["weights"])


# ---------------------------------------------------------------- trips
@router.get("/trips")
def trips():
    return store().list_trips()


@router.post("/trips")
def save_trip(req: S.TripSave):
    return store().save_trip(req.name, req.plan, req.trip_id, req.versions)


@router.get("/trips/{tid}")
def get_trip(tid: str):
    t = store().get_trip(tid)
    if not t:
        raise HTTPException(404, "Trip not found")
    return t


@router.delete("/trips/{tid}")
def delete_trip(tid: str):
    if not store().delete_trip(tid):
        raise HTTPException(404, "Trip not found")
    return dict(deleted=tid)


# ---------------------------------------------------------------- chat
@router.post("/chat")
def chat(req: S.ChatRequest):
    st = store()
    sid = req.session_id or uuid.uuid4().hex[:12]
    state = st.load_session(sid) or chat_mod.new_state()
    if req.plan and req.plan.get("days") and req.plan.get("prefs"):
        state["plan"] = req.plan
        state["prefs"] = {**state["prefs"], **req.plan["prefs"]}
        state["focus"] = state.get("focus") or req.plan.get("destination_id")
    reply, new_state = chat_mod.respond(get_engine(), state, req.message)
    st.save_session(sid, new_state)
    st.add_message(sid, "user", req.message)
    st.add_message(sid, "assistant", reply["text"], dict(intent=reply["intent"], entities=reply["entities"], suggestions=reply["suggestions"], understood=reply.get("understood"),
                                                         actions=[{k: v for k, v in a.items() if k != "plan"} | ({"plan_destination": a["plan"]["destination_name"]} if "plan" in a else {}) for a in reply["actions"]]))
    return dict(session_id=sid, reply=reply, prefs=new_state["prefs"], plan=new_state.get("plan"), previous_plan=new_state.get("previous_plan"), focus=_focus(new_state))


def _focus(state: dict) -> dict | None:
    fid = state.get("focus")
    d = get_engine().ds.destinations.get(fid) if fid else None
    return dict(id=fid, name=d["name"]) if d else None


@router.get("/chat/summaries")
def chat_summaries(ids: str = Query("", max_length=1000)):
    """Conversation list for the sidebar. The browser supplies its own session ids, so no one can enumerate other sessions."""
    return store().session_summaries([i for i in ids.split(",") if i.strip().isalnum()])


@router.get("/chat/{sid}")
def chat_history(sid: str):
    state = store().load_session(sid)
    if state is None:
        raise HTTPException(404, "Session not found")
    return dict(session_id=sid, messages=store().messages(sid), prefs=state["prefs"], plan=state.get("plan"), previous_plan=state.get("previous_plan"), focus=_focus(state))


@router.put("/chat/{sid}/prefs")
def chat_prefs(sid: str, req: S.PrefsPatch):
    state = store().load_session(sid) or chat_mod.new_state()
    patch = dict(req.prefs)
    if "destination" in patch:          # the destination the conversation is "about" (what 'there' refers to)
        v = patch.pop("destination")
        did = get_engine().ds.resolve_destination(str(v)) if v else None
        if v and not did:
            raise HTTPException(400, f"I do not have a destination called '{v}'.")
        state["focus"] = did
    try:
        merged = Preferences(**{**state["prefs"], **patch}).model_dump()
    except Exception as ex:
        raise HTTPException(400, f"Invalid preferences: {ex}")
    state["prefs"] = merged
    store().save_session(sid, state)
    return dict(session_id=sid, prefs=merged, focus=_focus(state))


@router.delete("/chat/{sid}")
def chat_reset(sid: str):
    store().delete_session(sid)
    return dict(reset=True)


# ---------------------------------------------------------------- knowledge base, search, ML, demo
@router.get("/kb/stats")
def kb_stats():
    return get_engine().kb.stats()


@router.get("/kb/facts")
def kb_facts(s: str | None = None, p: str | None = None, o: str | None = None, limit: int = Query(100, ge=1, le=500)):
    fs = get_engine().kb.query(s=s, p=p, o=o)
    return dict(total=len(fs), facts=[f.as_dict() for f in fs[:limit]])


@router.get("/kb/entity/{eid}")
def kb_entity(eid: str):
    d = get_engine().kb.describe(eid)
    if d["type"] is None:
        raise HTTPException(404, "Unknown entity")
    return d


@router.get("/kb/rules")
def kb_rules():
    return get_engine().rules.describe()


@router.get("/search/route")
def search_route(start: str, goal: str, metric: str = Query("distance", pattern="^(distance|time)$")):
    e = get_engine()
    if start not in e.graph.coords or goal not in e.graph.coords:
        raise HTTPException(404, "Unknown node. Use origin or destination ids.")
    return e.route_demo(start, goal, metric)


@router.get("/ml/metrics")
def ml_metrics():
    m = ml_affinity.metrics()
    if m is None:
        raise HTTPException(404, "ML metrics not generated. Run: python -m app.ml.stravl_pipeline")
    return m


@router.post("/thinks")
def thinks(req: S.ThinksRequest):
    """One call that returns the live reasoning artefacts used by the 'How TripWise Thinks' page."""
    e = get_engine()
    prefs = req.prefs
    rec = e.recommend(prefs, top_n=6)
    out: dict = dict(recommendation=rec, rules=e.rules.describe(), kb_stats=e.kb.stats(), weights=e.cfg["weights"], ml=ml_affinity.metrics())
    if rec.get("needs_info") or not rec["ranked"]:
        return out
    top = rec["ranked"][0]
    out["kb_facts"] = e.kb.facts_for_destination(top["id"], 24)
    out["route"] = e.route_demo(prefs.origin, top["id"], "distance")
    try:
        p = e.plan(prefs.model_copy(update=dict(duration_days=prefs.duration_days or max(top["min_days"], 3))), top["id"])
        out["plan_summary"] = dict(destination=p["destination_name"], total=p["costs"]["total"], search=p["search"], notes=p["notes"], transport=p["transport"]["mode"])
        tight = Preferences(**{**p["prefs"], "budget": max(1500, round(p["costs"]["total"] * 0.7, -2))})
        p2 = dict(p, prefs=tight.model_dump())
        out["budget_demo"] = e.optimize(p2, relax=True) | dict(plan=None)
        rp = e.replan(p, dict(exclude_activities=["trekking"], pace="relaxed"))
        out["replan_demo"] = rp["summary"] if rp["ok"] else dict(error=rp["error"])
    except PlanError as ex:
        out["plan_error"] = str(ex)
    return out
