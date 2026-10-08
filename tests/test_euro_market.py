"""Unit tests for the European market helpers (timelines -> boards -> Pinnacle fair prices)."""
import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from features.euro_market import board_at, close_board, fair_curve, fair_p


def _t(s):
    return pd.Timestamp(s, tz="UTC")


def _ladder(fid, book, t, mu=170.0, sigma=15.0, margin=0.03, lines=(166.5, 168.5, 170.5, 172.5), active=True):
    rows = []
    for x in lines:
        p_over = norm.cdf((mu - x) / sigma)
        for side, p in (("over", p_over), ("under", 1 - p_over)):
            rows.append({"fixture_id": fid, "book": book, "line": x, "side": side, "t": _t(t),
                         "price": 1 / (p * (1 + margin)), "active": active, "limit": None,
                         "start": _t("2026-03-10 19:00")})
    return rows


def test_fair_curve_recovers_mean_and_sigma():
    B = pd.DataFrame(_ladder("g1", "pinnacle", "2026-03-10 09:00", mu=171.3, sigma=15.0))
    C = fair_curve(B).set_index("fixture_id")
    assert C.at["g1", "fair_mu"] == pytest.approx(171.3, abs=0.05)
    assert 1 / C.at["g1", "b"] == pytest.approx(15.0, rel=0.02)
    p = fair_p(C.reset_index(), ["g1", "g1"], [171.3, 160.5], ["over", "under"])
    assert p[0] == pytest.approx(0.5, abs=0.01) and p[1] == pytest.approx(1 - norm.cdf(10.8 / 15), abs=0.01)


def test_board_at_uses_price_in_force_and_drops_suspended():
    T = pd.DataFrame(_ladder("g1", "x", "2026-03-10 09:00", mu=170) + _ladder("g1", "x", "2026-03-10 12:00", mu=174)
                     + _ladder("g1", "y", "2026-03-10 09:00") + _ladder("g1", "y", "2026-03-10 11:00", active=False))
    B = board_at(T, pd.Series({"g1": _t("2026-03-10 11:30")}))
    assert set(B.book) == {"x"}                                            # y suspended at 11:00
    assert fair_curve(B, book="x").fair_mu.iloc[0] == pytest.approx(170, abs=0.05)   # the 12:00 move is later


def test_close_board_keeps_lines_suspended_just_before_tip():
    T = pd.DataFrame(_ladder("g1", "x", "2026-03-10 09:00", lines=(170.5,))
                     + _ladder("g1", "x", "2026-03-10 10:00", lines=(172.5,))
                     + _ladder("g1", "x", "2026-03-10 11:00", lines=(172.5,), active=False)        # withdrawn early
                     + _ladder("g1", "x", "2026-03-10 18:55", lines=(170.5,), active=False))       # pre-tip suspension
    C = close_board(T)
    assert set(C.line) == {170.5}
