import numpy as np
import pandas as pd

from app.ml import stravl_pipeline as sp


def make_users(n=400, seed=0):
    """Synthetic users whose 'yes' swipes depend on experience: beach lovers like even-numbered destinations."""
    rng = np.random.default_rng(seed); rows = []
    for i in range(n):
        beach = rng.random() < 0.5
        yes = [int(d) for d in rng.choice(range(0, 20, 2) if beach else range(1, 20, 2), 4, replace=False)]
        no = [int(d) for d in rng.choice(range(1, 20, 2) if beach else range(0, 20, 2), 4, replace=False)]
        rows.append(dict(id=str(i), form_f="['0']" if beach else "['5']", form_g="['2']" if beach else "['0']", form_h="['1']", form_i="['1']", form_j="['1']",
                         yes_swipes=str(yes), no_swipes=str(no)))
    return sp.prepare_users(pd.DataFrame(rows))


def test_parsing_is_robust():
    assert sp.parse_list("['0', '2']") == [0, 2] and sp.parse_list("[837, 779]") == [837, 779]
    assert sp.parse_list(float("nan")) == [] and sp.parse_list("not a list") == [] and sp.parse_list("[") == []


def test_profiles_use_training_users_only_and_model_beats_chance():
    users = make_users()
    report, model = sp.train_and_evaluate(users, n_dest=20, max_train_pairs=5000, max_test_pairs=2000)
    assert report["n_users_train"] + report["n_users_test"] == len(users)                       # split by user, nothing dropped
    assert report["models"]["logistic_regression (deployed)"]["roc_auc"] > 0.8
    # leakage check: a destination's profile must change when a test-only user is added to the profile data
    tr = users.iloc[:300]
    p_tr = sp.build_profiles(tr, 20); p_all = sp.build_profiles(users, 20)
    assert not np.allclose(p_tr["yes_n"], p_all["yes_n"])
    # pure-numpy inference reproduces a sensible ordering
    exp = np.zeros(8, np.float32); exp[0] = 1; scn = np.zeros(8, np.float32); scn[2] = 1
    assert sp.score_with_model(model, exp, scn, 1.0, 1.0, 0) > sp.score_with_model(model, exp, scn, 1.0, 1.0, 1)
    assert report["limitations"]
