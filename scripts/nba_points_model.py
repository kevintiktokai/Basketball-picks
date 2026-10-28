"""NBA player points: a probability model for points props, tested season by season.

For every player-game it forecasts points from that player's EARLIER games only (recent scoring,
minutes, shot volume, last game's role, rest, home/away, the team's and the opponent's scoring so
far), then turns the forecast into P(over L) for any line L. Walk-forward: each season is predicted
by a model fitted only on earlier seasons (2022-23 .. 2025-26 tested; 2021-22 is warm-up).

What this measures: how well points can be forecast and whether the probabilities are honest
(calibrated). What it cannot measure: profit. That needs the books' historical prop lines, which no
free source has (reports/nba_points_model.md, "Next step").

Data: ESPN player box scores via sportsdataverse/hoopR-nba-data (data/raw/nba_player, SHA256SUMS).
Prop universe: a player with 5+ games this season averaging 20+ minutes and 8+ points (recent form).
Writes reports/nba_points_model.md and reports/nba_points_model.json.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from backtest.analysis import df_to_md
from config_loader import ROOT, log_experiment

RAW = ROOT / "data" / "raw" / "nba_player"
SEASONS = [2022, 2023, 2024, 2025, 2026]              # ESPN season = year it ends
TEST = [2023, 2024, 2025, 2026]
COLS = ["game_id", "season", "season_type", "game_date", "athlete_id", "athlete_display_name", "team_id", "minutes",
        "points", "field_goals_attempted", "free_throws_attempted", "three_point_field_goals_attempted", "turnovers",
        "starter", "did_not_play", "home_away", "team_score", "opponent_team_score", "opponent_team_id"]
FEATS = ["pts_ewm", "pts_l5", "pts_season", "min_ewm", "min_l5", "ppm_ewm", "use_ewm", "fta_ewm", "tpa_ewm",
         "pts_sd", "started_last", "n_season", "home", "rest", "team_for", "team_against", "opp_against",
         "missed_last", "prev_ppm", "prev_min"]
SEASON_LABEL = {s: f"{s - 1}-{str(s)[2:]}" for s in SEASONS + [2027]}


def load() -> pd.DataFrame:
    b = pd.concat([pd.read_parquet(RAW / f"player_box_{s}.parquet", columns=COLS) for s in SEASONS],
                  ignore_index=True)
    b = b[b.season_type.isin([2, 3])].copy()
    b["date"] = pd.to_datetime(b.game_date)
    for c in ("minutes", "points", "field_goals_attempted", "free_throws_attempted",
              "three_point_field_goals_attempted", "turnovers"):
        b[c] = pd.to_numeric(b[c], errors="coerce")
    b["played"] = (b.minutes.fillna(0) > 0) & ~b.did_not_play.fillna(False).astype(bool)
    return b.drop_duplicates(["game_id", "athlete_id"])


def features(b: pd.DataFrame) -> pd.DataFrame:
    """Point-in-time features: every value uses only games before the row's date."""
    # team schedule: rest days, and whether the player sat out his team's previous game
    tg = b.drop_duplicates(["team_id", "game_id"])[["team_id", "game_id", "date", "season", "team_score",
                                                    "opponent_team_score", "opponent_team_id"]].sort_values("date")
    tg["rest"] = tg.groupby("team_id").date.diff().dt.days.clip(upper=7)
    tg["prev_game"] = tg.groupby(["team_id", "season"]).game_id.shift(1)
    # team scoring environment so far this season (prior games only)
    for col, name in (("team_score", "team_for"), ("opponent_team_score", "team_against")):
        tg[name] = tg.groupby(["team_id", "season"])[col].transform(lambda s: s.shift(1).expanding().mean())
    opp = tg.set_index(["team_id", "game_id"]).team_against
    g = b[b.played].sort_values(["athlete_id", "date"]).copy()
    g = g.merge(tg[["team_id", "game_id", "rest", "prev_game", "team_for", "team_against"]], on=["team_id", "game_id"])
    g["opp_against"] = opp.reindex(pd.MultiIndex.from_arrays([g.opponent_team_id, g.game_id])).values
    played_keys = set(zip(g.athlete_id, g.game_id))
    g["missed_last"] = [float((a, p) not in played_keys) if pd.notna(p) else np.nan
                        for a, p in zip(g.athlete_id, g.prev_game)]
    g["use"] = g.field_goals_attempted + 0.44 * g.free_throws_attempted + g.turnovers
    a = g.groupby("athlete_id")
    ewm = lambda col: a[col].transform(lambda s: s.shift(1).ewm(halflife=8, min_periods=1).mean())   # noqa: E731
    g["pts_ewm"], g["min_ewm"] = ewm("points"), ewm("minutes")
    g["ppm_ewm"] = g.pts_ewm / g.min_ewm.replace(0, np.nan)
    g["use_ewm"] = ewm("use") / g.min_ewm.replace(0, np.nan)
    g["fta_ewm"], g["tpa_ewm"] = ewm("free_throws_attempted"), ewm("three_point_field_goals_attempted")
    g["pts_l5"] = a.points.transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    g["min_l5"] = a.minutes.transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    g["pts_sd"] = a.points.transform(lambda s: s.shift(1).rolling(20, min_periods=5).std())
    g["started_last"] = a.starter.shift(1).astype(float)
    s = g.groupby(["athlete_id", "season"])
    g["n_season"] = s.cumcount()
    g["pts_season"] = s.points.transform(lambda x: x.shift(1).expanding().mean())
    per = g.groupby(["athlete_id", "season"]).agg(pts=("points", "sum"), mins=("minutes", "sum"))
    per["ppm"] = per.pts / per.mins
    per["mpg"] = per.mins / g.groupby(["athlete_id", "season"]).size()
    prev = per.reset_index().assign(season=lambda x: x.season + 1).set_index(["athlete_id", "season"])
    idx = pd.MultiIndex.from_arrays([g.athlete_id, g.season])
    g["prev_ppm"], g["prev_min"] = prev.ppm.reindex(idx).values, prev.mpg.reindex(idx).values
    g["home"] = (g.home_away == "home").astype(float)
    g["prop"] = (g.n_season >= 5) & (g.min_ewm >= 20) & (g.pts_ewm >= 8)
    return g


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, seed: int = 0):
    import lightgbm as lgb
    params = dict(n_estimators=500, learning_rate=0.03, num_leaves=31, min_child_samples=200, subsample=0.8,
                  subsample_freq=1, colsample_bytree=0.8, reg_lambda=10.0, random_state=seed, verbose=-1)
    tr = train[train.n_season >= 1]
    # out-of-fold residuals on the training seasons give an honest spread and shape
    oof = np.full(len(tr), np.nan)
    folds = tr.season.values.copy()
    if len(np.unique(folds)) < 2:                                  # one training season: split it in two halves
        folds = (tr.date >= tr.date.median()).astype(int).values
    for f in np.unique(folds):
        m = lgb.LGBMRegressor(**params).fit(tr.loc[folds != f, FEATS], tr.points[folds != f])
        oof[folds == f] = m.predict(tr.loc[folds == f, FEATS])
    model = lgb.LGBMRegressor(**params).fit(tr[FEATS], tr.points)
    mu = np.clip(model.predict(test[FEATS]), 0.5, None)
    ok = tr.prop.values & np.isfinite(oof)
    r, m0 = tr.points.values[ok] - oof[ok], np.clip(oof[ok], 0.5, None)
    # spread grows with the forecast: sd = a + b * sqrt(mu), fitted on |residual| by bins
    bins = pd.qcut(m0, 20, duplicates="drop")
    sd_bin = pd.Series(r).groupby(bins).std().values
    mu_bin = pd.Series(m0).groupby(bins).mean().values
    b1, a1 = np.polyfit(np.sqrt(mu_bin), sd_bin, 1)
    sd_tr = a1 + b1 * np.sqrt(m0)
    z = np.sort(r / sd_tr)                                          # empirical shape (skew of scoring)
    sd = a1 + b1 * np.sqrt(mu)
    return mu, sd, z


def p_over(mu, sd, z, line):
    """P(points > line) from the empirical standardized-residual distribution."""
    k = (np.asarray(line) - mu) / sd
    return 1 - np.searchsorted(z, k, side="right") / len(z)


def main():
    b = load()
    g = features(b)
    rows, calib, months, by_role = [], [], [], []
    preds = []
    for s in TEST:
        train, test = g[g.season < s], g[g.season == s]
        mu, sd, z = fit_predict(train, test)
        T = test.assign(mu=mu, sd=sd)
        P = T[T.prop]
        err = P.points - P.mu
        naive_ewm, naive_season = P.points - P.pts_ewm, P.points - P.pts_season
        rows.append({"season": SEASON_LABEL[s], "player-games": len(P), "per day": len(P) / P.date.nunique(),
                     "model error (avg pts)": err.abs().mean(), "recent average error": naive_ewm.abs().mean(),
                     "season average error": naive_season.abs().mean(), "bias": err.mean(),
                     "inside 50% range": float(np.mean(np.abs(err) <= 0.674 * P.sd)),
                     "inside 80% range": float(np.mean(np.abs(err) <= 1.2816 * P.sd))})
        # calibration at lines around the player's recent average (where books set them)
        base = np.floor(P.pts_ewm.values) + 0.5
        for k in range(-4, 4):
            L = base + k
            p = p_over(P.mu.values, P.sd.values, z, L)
            calib.append(pd.DataFrame({"season": SEASON_LABEL[s], "p": p, "over": (P.points.values > L).astype(float)}))
        mo = P.assign(month=P.date.dt.to_period("M").astype(str))
        months.append(mo.groupby("month").apply(lambda x: pd.Series({"player-games": len(x),
                                                                     "model error": (x.points - x.mu).abs().mean(),
                                                                     "recent average error": (x.points - x.pts_ewm).abs().mean()}))
                      .assign(season=SEASON_LABEL[s]).reset_index())
        P = P.assign(role=pd.cut(P.pts_ewm, [0, 12, 18, 24, 99], labels=["8-12 pts", "12-18 pts", "18-24 pts", "24+ pts"]))
        by_role.append(P.groupby("role").apply(lambda x: pd.Series({"player-games": len(x),
                                                                    "model error": (x.points - x.mu).abs().mean(),
                                                                    "spread (sd)": x.sd.mean()}))
                       .assign(season=SEASON_LABEL[s]).reset_index())
        preds.append(P[["season", "date", "athlete_display_name", "points", "mu", "sd", "pts_ewm"]])
    R = pd.DataFrame(rows)
    C = pd.concat(calib)
    C["bin"] = pd.cut(C.p, [0, .2, .3, .4, .45, .5, .55, .6, .7, .8, 1.0])
    CB = C.groupby("bin").agg(predicted=("p", "mean"), happened=("over", "mean"), n=("p", "size")).reset_index()
    CB["bin"] = CB["bin"].astype(str)
    big = C[(C.p >= 0.6) | (C.p <= 0.4)]
    sharp = {"share of lines where the model says 60%+ either way": float(len(big) / len(C)),
             "those calls came true": float(np.mean(np.where(big.p >= 0.6, big.over, 1 - big.over)))}
    MO = pd.concat(months)
    RO = pd.concat(by_role)
    out = {"seasons": rows, "calibration": CB.to_dict("records"), "sharp": sharp}
    (ROOT / "reports" / "nba_points_model.json").write_text(json.dumps(out, indent=1, default=str))
    lines = ["# NBA player points: probability model, season by season\n",
             "Each season forecast by a model fitted only on earlier seasons; every forecast uses only the player's "
             "earlier games. Prop universe: 5+ games this season, 20+ minutes and 8+ points a game recently. "
             "Errors are average absolute misses in points.\n",
             df_to_md(R, "{:.3f}"), "",
             "Are the probabilities honest? Lines at every half-point from 4 below to 3 above each player's recent "
             "average (where books set them), all seasons pooled:\n", df_to_md(CB, "{:.3f}"), "",
             f"Strong calls: the model said 60%+ for one side on {sharp['share of lines where the model says 60%+ either way']:.0%} "
             f"of those lines, and it happened {sharp['those calls came true']:.1%} of the time. Against real book lines "
             "this share would be much smaller: books set lines nearer the true middle than a recent average does.\n",
             "By scoring role:\n", df_to_md(RO, "{:.3f}"), "",
             "Through the season (model error by month):\n", df_to_md(MO, "{:.3f}"), ""]
    (ROOT / "reports" / "nba_points_model.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))
    pd.concat(preds).to_parquet(ROOT / "data" / "processed" / "nba_points_preds.parquet", index=False)
    log_experiment("nba_points_model", {"seasons": SEASONS, "test": TEST, "feats": FEATS}, out)


if __name__ == "__main__":
    main()
