from app.ai.recommendation import Recommender
from app.ai.knowledge_base import build_kb
from app.ai.rule_engine import RuleEngine
from app.config import load_config
from app.schemas.prefs import Preferences


def rec_of(ds):
    cfg = load_config()
    return Recommender(ds, build_kb(ds), RuleEngine(cfg), cfg)


def test_budget_filtering_excludes_unaffordable_destinations(ds):
    """#1 Hard budget constraint: destinations whose cheapest plan exceeds the budget are excluded with a reason."""
    r = rec_of(ds)
    out = r.recommend(Preferences(origin="orig", budget=6000, duration_days=3, travellers=2), top_n=10)
    ids_ok = {x["id"] for x in out["ranked"]}
    excl = {e["id"]: e["excluded_reasons"] for e in out["excluded"]}
    assert "coldc" in excl and any("exceeds your budget" in s for s in excl["coldc"])
    for x in out["ranked"]:
        assert x["cost"]["floor"] <= 6000
    big = rec_of(ds).recommend(Preferences(origin="orig", budget=500000, duration_days=3, travellers=2), top_n=10)
    assert len(big["ranked"]) > len(ids_ok)


def test_no_result_gives_relaxation_advice(ds):
    out = rec_of(ds).recommend(Preferences(origin="orig", budget=500, duration_days=3), top_n=5)
    assert out["ranked"] == [] and out["relaxation"] and "No destination" in out["message"]
    assert any("budget" in t.lower() for t in out["relaxation"])


def test_preference_ranking_prefers_matching_destination(ds):
    """#2 Interest + climate preference ranks the matching destination first, with a 0-100 score and explanation."""
    r = rec_of(ds)
    out = r.recommend(Preferences(origin="orig", budget=40000, duration_days=3, travellers=2, climate="cool", interests=["nature", "mountains"]), top_n=4)
    top = out["ranked"][0]
    assert top["id"] == "hilla" and 0 <= top["match_score"] <= 100
    assert all(0 <= x["match_score"] <= 100 for x in out["ranked"])
    assert "Hill A" in top["explanation"] and "estimates" in top["explanation"].lower()
    beach = r.recommend(Preferences(origin="orig", budget=40000, duration_days=4, travellers=2, interests=["beaches", "food"]), top_n=4)["ranked"][0]
    assert beach["id"] == "beachb"


def test_ranking_is_reproducible_and_random_only_when_requested(ds):
    r = rec_of(ds)
    p = Preferences(origin="orig", budget=40000, duration_days=3, interests=["nature"])
    a = [x["id"] for x in r.recommend(p)["ranked"]]
    assert a == [x["id"] for x in r.recommend(p)["ranked"]]
    s1 = [x["match_score"] for x in r.recommend(p.model_copy(update=dict(randomize=True, seed=1)))["ranked"]]
    s2 = [x["match_score"] for x in r.recommend(p.model_copy(update=dict(randomize=True, seed=2)))["ranked"]]
    assert s1 != s2


def test_hard_constraints_duration_and_accessibility(ds):
    r = rec_of(ds)
    out = r.recommend(Preferences(origin="orig", budget=80000, duration_days=2, accessibility_required=True, travellers=2), top_n=10)
    excl = {e["id"]: " ".join(e["excluded_reasons"]) for e in out["excluded"]}
    assert "needs at least 3 days" in excl["beachb"]            # duration hard constraint
    assert "accessibility" in excl["coldc"]                     # mandatory accessibility
    assert all(x["id"] != "coldc" for x in out["ranked"])


def test_unspecified_preferences_renormalise_not_penalise(ds):
    out = rec_of(ds).recommend(Preferences(origin="orig", duration_days=3), top_n=4)
    comps = out["ranked"][0]["components"]
    assert comps["interest"]["status"] == "not_specified" and comps["budget"]["status"] == "not_specified"


def test_origin_required(ds):
    out = rec_of(ds).recommend(Preferences(budget=5000))
    assert out["needs_info"] == ["origin"]


def test_weights_are_configurable(ds):
    cfg = load_config(); kb = build_kb(ds)
    p = Preferences(origin="orig", budget=40000, duration_days=4, climate="warm", interests=["nature", "mountains"])
    default_top = Recommender(ds, kb, RuleEngine(cfg), cfg).recommend(p)["ranked"][0]
    assert default_top["id"] == "hilla"                       # interests dominate with the default weights
    cfg2 = load_config(); cfg2["weights"] = dict(interest=0, budget=0, climate=1, duration=0, convenience=0, style=0)
    alt_top = Recommender(ds, kb, RuleEngine(cfg2), cfg2).recommend(p)["ranked"][0]
    assert alt_top["id"] == "beachb"                          # climate-only weighting picks the warm destination
    assert alt_top["base_score"] == 100 * alt_top["components"]["climate"]["score"]


def test_exclusions_that_remove_attractions_exclude_but_sparse_data_does_not(ds):
    r = rec_of(ds)
    out = r.recommend(Preferences(origin="orig", budget=80000, duration_days=4, travellers=2, excluded_activities=["shopping", "food", "beaches"]), top_n=10)
    excl = {e["id"]: " ".join(e["excluded_reasons"]) for e in out["excluded"]}
    assert "beachb" in excl and "remain after your exclusions" in excl["beachb"]
    sparse = r.recommend(Preferences(origin="orig", budget=80000, duration_days=4, travellers=2), top_n=10)
    b = next(x for x in sparse["ranked"] if x["id"] == "beachb")
    assert any("lists only 3 attraction" in l for l in b["limitations"])
