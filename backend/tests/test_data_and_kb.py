import json

from app.ai.data_loader import load_dataset
from app.ai.knowledge_base import build_kb
from app.ai.recommendation import Recommender
from app.ai.rule_engine import RuleEngine
from app.config import load_config
from app.schemas.prefs import Preferences


def test_missing_and_invalid_dataset_fields_are_handled(tmp_path, fixture_dir):
    """#3 Missing/invalid fields are repaired or dropped and reported - never silently trusted."""
    for f in fixture_dir.glob("*.json"):
        (tmp_path / f.name).write_text(f.read_text())
    atts = json.loads((tmp_path / "attractions.json").read_text())
    atts.append(dict(id="x1", destination_id="hilla", name="No Duration", tags=["nature"], lat=11.4, lon=76.7, fee_inr=None, intensity=1))   # missing duration + fee
    atts.append(dict(id="x2", destination_id="hilla", name="Bad Coords", tags=["nature"], lat=999, lon=76.7, duration_min=60))                 # invalid coordinates
    atts.append(dict(id="x3", destination_id="nowhere", name="Orphan", tags=["nature"], lat=11.4, lon=76.7, duration_min=60))                    # unknown destination
    atts.append(dict(id="x4", destination_id="hilla", name="Lake Walk", tags=["nature"], lat=11.4, lon=76.7, duration_min=60))                   # duplicate name
    (tmp_path / "attractions.json").write_text(json.dumps(atts))
    d = load_dataset(tmp_path)
    assert d.attractions["x1"]["duration_min"] == 60 and d.attractions["x1"]["fee_known"] is False
    assert not {"x2", "x3", "x4"} & set(d.attractions)
    assert any("Bad Coords" in i for i in d.issues) and any("duplicate" in i for i in d.issues) and any("unknown destination" in i for i in d.issues)
    assert any("climate missing" in i for i in d.issues)  # heritd has no climate


def test_missing_destination_data_is_not_a_free_match(ds):
    """#3 A missing climate scores the configured low value and is flagged as unverified."""
    cfg = load_config()
    rec = Recommender(ds, build_kb(ds), RuleEngine(cfg), cfg)
    p = Preferences(origin="orig", climate="hot", duration_days=3, budget=40000)
    r = {x["id"]: x for x in rec.recommend(p, top_n=10)["ranked"]}
    c = r["heritd"]["components"]["climate"]
    assert c["status"] == "missing_data" and c["score"] == cfg["missing_component_score"]
    assert any("unverified" in l or "missing" in l for l in r["heritd"]["limitations"])


def test_knowledge_base_queries(ds):
    """#4 Typed triples, pattern queries, inverse lookups and grounded facts."""
    kb = build_kb(ds)
    assert kb.one("hilla", "HAS_CLIMATE") == "cool"
    assert "nature" in kb.objects("hilla", "HAS_ACTIVITY")
    attrs = kb.objects("hilla", "CONTAINS_ATTRACTION")
    assert len(attrs) == 7 and all(kb.one(a, "LOCATED_IN") == "hilla" for a in attrs)
    assert set(kb.subjects("HAS_CLIMATE", "cool")) == {"hilla"}
    assert kb.query(s="hilla", p="HAS_CLIMATE", o="warm") == []
    trek = next(a for a in attrs if kb.entity_label[a] == "Summit Trek")
    assert kb.one(trek, "HAS_ESTIMATED_DURATION") == 150 and kb.one(trek, "HAS_INTENSITY") == 3
    assert kb.query(p="CONNECTS", s="orig") and kb.describe("hilla")["type"] == "destination"
    assert kb.attraction_count_with_tag("hilla", "nature") == 4
    near = kb.query(p="LOCATED_NEAR")
    assert near and all(f.provenance.startswith("computed") for f in near)  # derived facts carry provenance
    assert kb.stats()["n_facts"] == len(kb.facts)


def test_rules_are_inspectable_and_explained(ds):
    cfg = load_config()
    re_ = RuleEngine(cfg)
    desc = re_.describe()
    assert {"R1_COOL_CLIMATE", "R3_ACCESSIBLE_TRAVEL", "R7_PROXIMITY", "R6_OVER_BUDGET"} <= {r["id"] for r in desc}
    assert all(r["if"].startswith("IF") and r["then"].startswith("THEN") for r in desc)
    p = Preferences(origin="orig", climate="cool", interests=["nature"])
    adj = {a["rule_id"]: a for a in re_.evaluate_ranking(p, ds.destinations["hilla"], dict(one_way_hours=5, tag_counts={"nature": 4}))}
    assert adj["R1_COOL_CLIMATE"]["fired"] and adj["R1_COOL_CLIMATE"]["points"] > 0 and adj["R1_COOL_CLIMATE"]["reason"]
    assert adj["R5_NATURE"]["fired"]
    hot = {a["rule_id"]: a for a in re_.evaluate_ranking(Preferences(origin="orig", climate="cold"), ds.destinations["beachb"], dict(one_way_hours=5, tag_counts={}))}
    assert hot["R1B_CLIMATE_CONTRADICTION"]["fired"] and hot["R1B_CLIMATE_CONTRADICTION"]["points"] < 0
