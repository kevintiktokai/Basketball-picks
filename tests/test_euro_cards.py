"""Unit tests for the European two-leg card builder."""
import datetime as dt

import pandas as pd
import pytest

from backtest.euro_cards import cards, summary

D1, D2 = dt.date(2026, 2, 1), dt.date(2026, 2, 2)


def _leg(fid, date, price, ev, *, book="1xbet", clv=0.02, win=True, agree=True, side="over", line=160.5):
    return {"fixture_id": fid, "date": date, "book": book, "line": line, "side": side, "price": price,
            "ev_now": ev, "clv": clv, "win": win, "model_agrees": agree}


CFG = {"leg_ev_min": 0.0, "leg_odds_band": (1.4, 1.9), "books": "all_soft", "model_agrees": False,
       "cards_per_date": "1"}


def test_best_pair_per_date_respects_odds_band_and_min_combined_odds():
    L = pd.DataFrame([_leg("a", D1, 1.60, 0.05), _leg("a", D1, 1.80, 0.09),       # best leg of game a: 1.80
                      _leg("b", D1, 1.50, 0.04), _leg("c", D1, 1.45, 0.08),
                      _leg("d", D1, 2.40, 0.30),                                      # outside the band
                      _leg("e", D2, 1.55, 0.03)])                                     # alone on its date
    C = cards(L, CFG)
    assert len(C) == 1
    r = C.iloc[0]
    assert {r.game_a, r.game_b} == {"a", "c"}                                         # 1.80*1.45 = 2.61 >= 2.5
    assert r.odds == pytest.approx(1.80 * 1.45) and r.ev == pytest.approx(1.09 * 1.08 - 1)


def test_all_disjoint_never_reuses_a_game_and_filters_apply():
    L = pd.DataFrame([_leg("a", D1, 1.70, 0.06), _leg("b", D1, 1.70, 0.05), _leg("c", D1, 1.70, 0.04),
                      _leg("d", D1, 1.70, 0.03), _leg("e", D1, 1.70, 0.02, agree=False),
                      _leg("f", D1, 1.70, 0.20, book="pinnacle")])                    # not a soft book
    C = cards(L, {**CFG, "cards_per_date": "all_disjoint"})
    games = list(C.game_a) + list(C.game_b)
    assert len(C) == 2 and len(games) == len(set(games)) and "f" not in games
    C2 = cards(L, {**CFG, "cards_per_date": "all_disjoint", "model_agrees": True})
    assert "e" not in set(C2.game_a) | set(C2.game_b)


def test_summary_profit_drawdown_and_losing_run():
    C = pd.DataFrame({"date": [D1, D1, D2, D2], "odds": [3.0, 3.0, 3.0, 3.0], "ev": 0.1, "clv": [0.05, -0.01, 0.02, 0.03],
                      "win": [False, False, True, False], "pnl": [-1.0, -1.0, 2.0, -1.0]})
    s = summary(C)
    assert s["profit (units)"] == -1.0 and s["max drawdown"] == 2.0 and s["longest losing run"] == 2
    assert s["CLV > 0"] == 0.75 and s["ROI"] == pytest.approx(-0.25)
