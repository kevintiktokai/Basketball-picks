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


def test_line_shopping_and_real_prices():
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from stage2b_test import american_to_decimal, best_open_for_side, median_open_price
    books = json.dumps({
        "dk": {"open": 140.5, "open_over": -110, "open_under": -110},
        "fd": {"open": 139.5, "open_over": -105, "open_under": -115},
        "mgm": {"open": 141.5, "open_over": -120, "open_under": +100},
    })
    line, dec, book = best_open_for_side(books, 1)       # Over: lowest total
    assert (line, book) == (139.5, "fd") and abs(dec - (1 + 100 / 105)) < 1e-9
    line, dec, book = best_open_for_side(books, -1)      # Under: highest total
    assert (line, book) == (141.5, "mgm") and abs(dec - 2.0) < 1e-9
    assert abs(median_open_price(books, 1, 140.5) - (1 + 100 / 110)) < 1e-9
    assert abs(float(american_to_decimal(150)) - 2.5) < 1e-9


def test_tempo_venue_term_restores_possessions_without_neutral_games():
    """Without neutral-site games the tempo intercept is collinear with the venue term; the
    locked default drops that term (~half-size possessions), venue_tempo=True keeps it."""
    from features.ratings import DailyRatings
    rng = np.random.default_rng(0)
    teams = [f"T{i}" for i in range(8)]
    rows = []
    for d in range(60):
        perm = rng.permutation(teams)
        for k in range(4):
            rows.append({"date": pd.Timestamp("2024-10-01") + pd.Timedelta(days=d), "season": "2024-25",
                         "home": perm[2 * k], "away": perm[2 * k + 1], "neutral": False,
                         "home_pts": 80 + rng.normal(0, 8), "away_pts": 78 + rng.normal(0, 8),
                         "poss": 72 + rng.normal(0, 3), "game_key": f"g{d}_{k}"})
    g = pd.DataFrame(rows)
    old = DailyRatings(half_life_days=60).run(g).rt_poss.dropna()
    new = DailyRatings(half_life_days=60, venue_tempo=True).run(g).rt_poss.dropna()
    assert abs(new.mean() - 72) < 1.5
    assert old.mean() < 50                                   # the documented legacy behaviour
