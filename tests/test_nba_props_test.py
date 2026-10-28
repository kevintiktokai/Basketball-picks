"""NBA props test (scripts/nba_props_test.py): reading a book's offer at a time, Pinnacle's no-vig
price, grading, and the name and team keys used to match players. Prices are invented."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import nba_props_test as t  # noqa: E402


def _prices():
    start = pd.Timestamp("2026-10-22T00:00:00Z")
    row = lambda book, line, side, h, price, active=True: {                          # noqa: E731
        "fixture_id": "f", "start": start, "book": book, "player_id": "7", "line": line, "side": side,
        "t": start - pd.Timedelta(hours=h), "price": price, "active": active}
    return pd.DataFrame([
        row("pinnacle", 20.5, "over", 5, 1.80), row("pinnacle", 20.5, "under", 5, 2.05),
        row("pinnacle", 20.5, "over", 2, 1.90, active=False),                          # line pulled 2h before
        row("pinnacle", 20.5, "under", 2, 1.95, active=False),
        row("pinnacle", 21.5, "over", 2, 1.95), row("pinnacle", 21.5, "under", 2, 1.90),
        row("1xbet", 20.5, "over", 4, 2.10), row("1xbet", 20.5, "under", 4, 1.70)])


def test_quotes_take_last_live_price_and_drop_pulled_lines():
    W = t.quotes(_prices(), 3.0)                                 # 3h before: 20.5 still live everywhere
    pin = W[W.book == "pinnacle"]
    assert list(pin.line) == [20.5] and float(pin.over.iloc[0]) == 1.80
    W = t.quotes(_prices(), 1.0)                                 # 1h before: Pinnacle moved to 21.5
    assert set(W[W.book == "pinnacle"].line) == {21.5}
    assert set(W[W.book == "1xbet"].line) == {20.5}


def test_pinnacle_fair_removes_the_margin():
    P = t.pinnacle_fair(t.quotes(_prices(), 3.0))
    io, iu = 1 / 1.80, 1 / 2.05
    assert np.isclose(P.p_fair.iloc[0], io / (io + iu))
    assert np.isclose(P.margin.iloc[0], io + iu - 1)


def test_grade_void_push_win_loss():
    D = pd.DataFrame({"side": ["over", "under", "over", "over"], "line": [20.5, 20.5, 20.0, 20.5],
                      "points": [25.0, 25.0, 20.0, np.nan], "played": [True, True, True, False],
                      "price": [1.9, 1.9, 1.9, 1.9]})
    G = t.grade(D)
    assert list(G.result) == ["won", "lost", "push", "void"]
    assert np.allclose(G.pnl, [0.9, -1.0, 0.0, 0.0])


def test_name_and_team_keys():
    assert t.norm("Hardaway Jr., Tim".split(",")[0]) == "hardaway"
    assert t.norm("Nikola Jokić") == "nikola jokic"
    assert t.norm("Michael Porter Jr.") == "michael porter"
    assert t.nickname("Portland Trail Blazers") == t.nickname("Trail Blazers") == "blazers"
    assert t.nickname("LA Clippers") == t.nickname("Los Angeles Clippers")
