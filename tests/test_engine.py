"""Unit tests for the probability, dependence and card-selection logic."""
import numpy as np
import pandas as pd
import pytest

from backtest.cards import SelectionParams, _double_profit, card_metrics, decide_slate
from backtest.dependence import joint_probability, required_individual_probability
from calibration.calibrate import Calibrator, wilson
from models.total_models import over_probability


def _day(ps, cons=None):
    n = len(ps)
    return pd.DataFrame({
        "game_id": [f"g{i}" for i in range(n)], "date": pd.Timestamp("2020-01-01"),
        "season": "2019-20", "p_cal": ps, "p_cons": cons if cons is not None else ps,
        "p_raw": ps, "line": 220.0, "proj_total": 230.0, "total": 0.0,
        "calibrated": True, "eligible_data": True,
    })


def test_joint_independent_is_product():
    assert joint_probability(0.7, 0.8, 0.0) == pytest.approx(0.56, abs=1e-4)


def test_joint_increases_with_positive_dependence():
    assert joint_probability(0.7, 0.7, 0.3) > joint_probability(0.7, 0.7, 0.0)


def test_required_probability_independent():
    assert required_individual_probability(0.60, 0.0) == pytest.approx(np.sqrt(0.6), abs=1e-3)


def test_card_released_only_when_conservative_joint_clears_target():
    sp = SelectionParams()
    assert decide_slate(_day([0.90, 0.88, 0.55]), sp).outcome == "TWO-PICK CARD"
    # strong calibrated marginals but weak conservative bounds -> no card
    d = decide_slate(_day([0.90, 0.88], cons=[0.70, 0.70]), sp)
    assert d.outcome != "TWO-PICK CARD"


def test_two_individually_strong_picks_do_not_force_a_card():
    sp = SelectionParams()
    d = decide_slate(_day([0.70, 0.70]), sp)        # 0.7*0.7 = 0.49 < 0.60
    assert d.outcome == "ONE QUALIFYING PICK"
    assert len(d.picks) == 1


def test_no_bet_when_nothing_qualifies():
    sp = SelectionParams()
    assert decide_slate(_day([0.52, 0.51, 0.50]), sp).outcome == "NO BET"


def test_best_pair_is_by_joint_probability_not_top_two_by_ev():
    sp = SelectionParams()
    d = decide_slate(_day([0.95, 0.90, 0.85]), sp)
    assert {p.game_id for p in d.picks} == {"g0", "g1"}


def test_double_profit_and_push():
    assert _double_profit(["W", "W"], 2.0) == pytest.approx(3.0)
    assert _double_profit(["W", "P"], 2.0) == pytest.approx(1.0)
    assert _double_profit(["W", "L"], 2.0) == -1.0


def test_card_metrics_counts():
    s = pd.DataFrame({"outcome": ["TWO-PICK CARD"] * 3 + ["NO BET"],
                      "card_wins": [2, 1, 0, np.nan], "card_2of2": [1, 0, 0, np.nan],
                      "singles_profit": [1.8, -0.1, -2, np.nan], "double_profit": [2.6, -1, -1, np.nan],
                      "joint_cal": [.7, .7, .7, np.nan], "joint_cons": [.62, .62, .62, np.nan]})
    m = card_metrics(s)
    assert (m["cards_2of2"], m["cards_1of2"], m["cards_0of2"]) == (1, 1, 1)
    assert m["rate_2of2"] == pytest.approx(1 / 3)


def test_over_probability_symmetry_and_push():
    p, push = over_probability(np.array([0.0]), np.array([220.5]), 18.0)
    assert p[0] == pytest.approx(0.5, abs=1e-6) and push[0] == 0
    p, push = over_probability(np.array([0.0]), np.array([220.0]), 18.0)
    assert push[0] > 0.01 and p[0] == pytest.approx(0.5, abs=1e-6)


def test_conservative_bound_below_point_estimate():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.4, 0.6, 5000)
    y = (rng.uniform(size=5000) < p).astype(int)
    c = Calibrator("none").fit(p, y)
    lb = c.lower_bound(np.array([0.55]))
    assert lb[0] < 0.55


def test_wilson():
    lo, hi = wilson(60, 100)
    assert lo < 0.6 < hi
