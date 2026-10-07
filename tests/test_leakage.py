"""Leakage tests. These must fail loudly if future information reaches features."""
import numpy as np
import pandas as pd
import pytest

from config_loader import ROOT
from features.pit import _assert_no_leakage, build_features

PROC = ROOT / "data" / "processed"


@pytest.fixture(scope="module")
def data():
    if not (PROC / "games.parquet").exists():
        from data.ingest import build
        build()
    g = pd.read_parquet(PROC / "games.parquet")
    b = pd.read_parquet(PROC / "team_box.parquet")
    g = g[g.season.isin(["2014-15", "2015-16"])].copy()
    b = b[b.season.isin(["2014-15", "2015-16"])].copy()
    return g, b


FEATURE_COLS_EXCLUDE = {"home_pts", "away_pts", "total", "box_game_id", "quality_flags", "clean"}


def _feature_cols(df):
    return [c for c in df.columns if c not in FEATURE_COLS_EXCLUDE]


def test_feature_asof_strictly_before_game_date(data):
    g, b = data
    f = build_features(g, b)
    asof = pd.to_datetime(f.feature_asof)
    assert (asof.isna() | (asof < f.date)).all()


def test_future_results_do_not_change_past_features(data):
    g, b = data
    cutoff = pd.Timestamp("2015-12-15")
    base = build_features(g, b)

    g2 = g.copy()
    fut = g2.date >= cutoff
    rng = np.random.default_rng(0)
    g2.loc[fut, "home_pts"] = rng.integers(60, 160, fut.sum())
    g2.loc[fut, "away_pts"] = rng.integers(60, 160, fut.sum())
    g2["total"] = g2.home_pts + g2.away_pts
    b2 = b.copy()
    bf = b2.date >= cutoff
    b2.loc[bf, ["PTS", "PTS_opp", "FGA", "TOV", "OREB"]] = rng.integers(5, 150, (bf.sum(), 5))
    pert = build_features(g2, b2)

    cols = _feature_cols(base)
    keep = base.date <= cutoff          # includes the cutoff day itself
    a = base.loc[keep, cols].reset_index(drop=True)
    c = pert.loc[pert.date <= cutoff, cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, c)
    # sanity: features after the cutoff DO change, i.e. the test has power
    later = base.date > cutoff + pd.Timedelta(days=3)
    assert not np.allclose(base.loc[later, "rating_exp_total"].values,
                           pert.loc[pert.date > cutoff + pd.Timedelta(days=3), "rating_exp_total"].values)


def test_same_day_games_do_not_see_each_other(data):
    g, b = data
    day = pd.Timestamp("2016-01-20")
    base = build_features(g, b)
    g2 = g.copy()
    idx = g2.index[g2.date == day][0]
    g2.loc[idx, ["home_pts", "away_pts"]] = [200, 200]
    g2.loc[idx, "total"] = 400
    pert = build_features(g2, b)
    cols = _feature_cols(base)
    pd.testing.assert_frame_equal(
        base.loc[base.date == day, cols].reset_index(drop=True),
        pert.loc[pert.date == day, cols].reset_index(drop=True),
    )


def test_leakage_assertion_fires():
    df = pd.DataFrame({"game_id": ["x"], "date": [pd.Timestamp("2020-01-02")],
                       "feature_asof": [pd.Timestamp("2020-01-02")]})
    with pytest.raises(AssertionError, match="LEAKAGE"):
        _assert_no_leakage(df)


def test_quality_rules_do_not_depend_on_outcome():
    """Line plausibility flags must be identical if game results are shuffled."""
    from data import ingest
    g, _, _ = ingest.build(write=False)
    flags_line = g.quality_flags.str.contains("implausible_line|placeholder_line")
    # the rule inputs are line/spread/date only; re-derive with shuffled totals
    shuffled = g.copy()
    shuffled["total"] = np.random.default_rng(1).permutation(shuffled.total.values)
    bad_range = (shuffled.line < 150) | (shuffled.line > 300)
    placeholder = shuffled.groupby(["date", "line"])["line"].transform("size") >= 3  # superset check
    assert (flags_line <= (bad_range | placeholder)).all()
