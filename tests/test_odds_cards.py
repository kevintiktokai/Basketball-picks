"""Unit tests for the odds-targeted card engine (stage 3)."""
import json

import numpy as np
import pandas as pd
import pytest

from backtest.odds_cards import (K_ALT, LegSet, american_to_decimal, best_main, odds_cards,
                                 settle)


def test_settlement_rules():
    assert settle(True, False, 1.6, True, False, 1.6) == pytest.approx(1.56)
    assert settle(True, False, 1.6, False, True, 1.6) == pytest.approx(0.6)   # push = void leg
    assert settle(False, True, 1.6, False, True, 1.6) == 0.0                  # both void
    assert settle(True, False, 1.6, False, False, 1.6) == -1.0


def test_best_main_picks_best_number_then_price():
    books = json.dumps({"a": {"open": 140.5, "open_over": -110, "open_under": -110},
                        "b": {"open": 139.5, "open_over": -120, "open_under": 100},
                        "c": {"open": 139.5, "open_over": -105, "open_under": -115}})
    line, dec, book = best_main(books, 1)
    assert (line, book) == (139.5, "c") and dec == pytest.approx(1 + 100 / 105)
    line, dec, book = best_main(books, -1)
    assert (line, book) == (140.5, "a")
    assert np.isnan(american_to_decimal(0)[0])


def _toy_legs(p_vals, odds_main=1.6):
    n, nk = len(p_vals), len(K_ALT) + 1
    frame = pd.DataFrame({"date": pd.Timestamp("2024-01-01"), "season": "2023-24",
                          "game_key": [f"g{i}" for i in range(n)]})
    thr = np.full((n, 2, nk), 140.5)
    p = np.zeros((n, 2, nk))
    p[:, 0, 0] = p_vals
    p[:, 1, 0] = 0.3
    pm = np.full((n, 2, nk), 0.999)            # alternates priced ~1.0 -> never chosen
    real = np.full((n, 2), odds_main)
    win = np.zeros((n, 2, nk), bool)
    win[:, 0, 0] = True
    push = np.zeros((n, 2, nk), bool)
    return LegSet(frame, thr, p, p.copy(), pm, pm.copy(), real, win, push)


def test_card_respects_floor_and_gate():
    L = _toy_legs([0.70, 0.68, 0.40])
    C = odds_cards(L, floor=2.5, margin=0.045)
    assert len(C) == 1
    c = C.iloc[0]
    assert c.combined_odds >= 2.5 and {c.game_a, c.game_b} == {"g0", "g1"}
    # same legs but a floor nobody can reach -> no card
    assert odds_cards(L, floor=3.0, margin=0.045).empty
    # weak legs: conservative EV <= 0 -> no card unless forced
    W = _toy_legs([0.55, 0.55, 0.50])
    assert odds_cards(W, floor=2.5, margin=0.045).empty
    assert len(odds_cards(W, floor=2.5, margin=0.045, force=True)) == 1


def test_best_main_ignores_outlier_books():
    books = json.dumps({"a": {"open": 166.5, "open_over": -110, "open_under": -110},
                        "b": {"open": 166.0, "open_over": -110, "open_under": -110},
                        "c": {"open": 167.0, "open_over": -110, "open_under": -110},
                        "stale": {"open": 145.5, "open_over": -110, "open_under": -110}})
    line, _, book = best_main(books, 1)
    assert (line, book) == (166.0, "b")              # the 145.5 outlier is never "best"
    line, _, book = best_main(books, 1, max_dev=None)
    assert book == "stale"                          # (guard off reproduces the old behaviour)
