"""NCAAB leakage tests: corrupting results (and later lines) must not change
any feature of games on or before the cutoff date, in any market frame."""
import numpy as np
import pandas as pd
import pytest

from config_loader import ROOT
from features.ncaab_features import build_ncaab_features, market_frame

PROC = ROOT / "data" / "processed"
OUTCOME_COLS = {"home_pts", "away_pts", "total", "first_half", "second_half", "home_1h", "away_1h",
                "home_2h_reg", "away_2h_reg", "resid", "over", "push", "outcome",
                "poss"}  # the game's own box possessions: post-game, never a model input


@pytest.fixture(scope="module")
def base():
    if not (PROC / "ncaab_games.parquet").exists():
        pytest.skip("run python -m data.ncaab_ingest first")
    g = pd.read_parquet(PROC / "ncaab_games.parquet")
    b = pd.read_parquet(PROC / "ncaab_box.parquet")
    g = g[g.season.isin(["2014-15", "2015-16"])].copy()
    b = b[b.espn_game_id.isin(g.espn_game_id.dropna())].copy()
    return g, b


def _perturb(g, b, cutoff):
    rng = np.random.default_rng(3)
    g2, b2 = g.copy(), b.copy()
    for c in ["home_pts", "away_pts", "home_1h", "away_1h", "line_close", "line_open"]:
        g2[c] = g2[c].astype(float)
    fut = g2.date >= cutoff
    n = int(fut.sum())
    g2.loc[fut, "home_pts"] = rng.integers(40, 110, n)
    g2.loc[fut, "away_pts"] = rng.integers(40, 110, n)
    later_mask = g2.date > cutoff
    # first halves of cutoff-day games are KNOWN at their half-time (the 2H market's bet
    # time), so only later dates' first halves are scrambled; cutoff-day finals are.
    g2.loc[later_mask, "home_1h"] = rng.integers(15, 40, int(later_mask.sum()))
    g2.loc[later_mask, "away_1h"] = rng.integers(15, 40, int(later_mask.sum()))
    g2["total"] = g2.home_pts + g2.away_pts
    g2["first_half"] = g2.home_1h + g2.away_1h
    g2["second_half"] = g2.total - g2.first_half
    later = g2.date > cutoff                      # lines of LATER dates also scrambled
    g2.loc[later, "line_close"] = g2.loc[later, "line_close"] + rng.normal(0, 8, int(later.sum()))
    g2.loc[later, "line_open"] = g2.loc[later, "line_open"] + rng.normal(0, 8, int(later.sum()))
    fut_ids = set(g.loc[fut, "espn_game_id"].dropna())
    bf = b2.espn_game_id.isin(fut_ids)
    for c in ["pts", "fga", "fgm", "fg3a", "fg3m", "fta", "oreb", "dreb", "tov", "poss",
              "fga_opp", "fgm_opp", "fg3a_opp", "fg3m_opp", "fta_opp", "oreb_opp", "dreb_opp", "tov_opp"]:
        b2[c] = b2[c].astype(float)
        b2.loc[bf, c] = b2.loc[bf, c] * rng.uniform(0.6, 1.4, int(bf.sum()))
    return g2, b2


@pytest.mark.parametrize("market", ["open", "close", "second_half"])
def test_ncaab_features_ignore_the_future(base, market):
    g, b = base
    cutoff = pd.Timestamp("2016-01-10")
    f1 = build_ncaab_features(write=False, games=g, box=b)
    g2, b2 = _perturb(g, b, cutoff)
    f2 = build_ncaab_features(write=False, games=g2, box=b2)
    m1 = market_frame(f1, market)
    m2 = market_frame(f2, market)
    numeric = m1.select_dtypes(include=["number", "bool", "datetime"]).columns
    cols = [c for c in numeric if c not in OUTCOME_COLS]
    a = m1[m1.date <= cutoff].set_index("game_key").sort_index()[cols]
    c = m2[m2.date <= cutoff].set_index("game_key").sort_index()[cols]
    pd.testing.assert_frame_equal(a, c, check_exact=False, rtol=1e-9, atol=1e-9)
    # power check: later features do change
    later1 = m1[m1.date > cutoff + pd.Timedelta(days=5)].set_index("game_key").sort_index()
    later2 = m2[m2.date > cutoff + pd.Timedelta(days=5)].set_index("game_key").sort_index()
    assert not np.allclose(later1.x_pts.values, later2.x_pts.loc[later1.index].values, equal_nan=True)
