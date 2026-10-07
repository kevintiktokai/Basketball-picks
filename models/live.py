"""Live / pre-game prediction using the LOCKED model.

Uses exactly the same feature builder, model class, calibration and card
engine as the backtest. History = processed games (+ optional user-supplied
recent results so the team states are current).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yaml

from backtest.cards import SelectionParams, decide_slate
from backtest.dependence import joint_probability
from calibration.calibrate import Calibrator
from config_loader import ROOT, load_config
from data.ingest import REGULAR_SEASON_END, TEAM_CODES
from features.pit import build_features
from models.total_models import FEATURE_SETS, add_derived, fit_model, over_probability

CODES = set(TEAM_CODES.values())


def season_of(d: pd.Timestamp) -> str:
    y = d.year if d.month >= 8 else d.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def _team(x: str) -> str:
    x = x.strip()
    if x.upper() in CODES:
        return x.upper()
    if x in TEAM_CODES:
        return TEAM_CODES[x]
    raise ValueError(f"unknown team '{x}' (use a 3-letter code such as BOS or a full name)")


def load_slate(path: str, date: str | None) -> pd.DataFrame:
    s = pd.read_csv(path)
    s.columns = [c.strip().lower() for c in s.columns]
    if "date" not in s:
        if date is None:
            raise ValueError("slate needs a 'date' column or --date")
        s["date"] = date
    s["date"] = pd.to_datetime(s["date"])
    s["home"] = s["home"].map(_team)
    s["away"] = s["away"].map(_team)
    s["line"] = s["line"].astype(float)
    s["odds"] = s.get("over_odds", pd.Series(1.909, index=s.index)).astype(float)
    if "home_spread" not in s:
        s["home_spread"] = np.nan
    return s


def predict_slate(slate: pd.DataFrame, extra_history: str | None = None):
    lock = yaml.safe_load((ROOT / "config" / "locked_model.yaml").read_text())
    m = lock["model"]
    sel = lock["selection"]
    games = pd.read_parquet(ROOT / "data" / "processed" / "games.parquet")
    if extra_history:
        ex = load_slate(extra_history, None)
        ex["home_pts"] = ex["home_pts"].astype(float)
        ex["away_pts"] = ex["away_pts"].astype(float)
        ex["total"] = ex.home_pts + ex.away_pts
        ex["season"] = ex.date.map(season_of)
        ex["game_id"] = ex.date.dt.strftime("%Y%m%d") + "_" + ex.away + "@" + ex.home
        ex["is_postseason"] = False
        ex["clean"] = True
        ex["quality_flags"] = ""
        games = pd.concat([games, ex[[c for c in games.columns if c in ex.columns]]], ignore_index=True)
    date = slate.date.min()
    hist = games[games.date < date]
    up = slate.copy()
    up["season"] = up.date.map(season_of)
    end = REGULAR_SEASON_END.get(up.season.iloc[0])
    up["is_postseason"] = up.date > pd.Timestamp(end) if end else False
    up["game_id"] = up.date.dt.strftime("%Y%m%d") + "_" + up.away + "@" + up.home
    up["home_pts"] = up["away_pts"] = up["total"] = 0.0     # placeholders; never used for features
    up["clean"] = True
    up["quality_flags"] = ""
    up["box_game_id"] = np.nan
    allg = pd.concat([hist, up[[c for c in hist.columns if c in up.columns]]], ignore_index=True)
    feats = add_derived(build_features(allg, None))
    feats = feats.merge(up[["game_id", "odds"]], on="game_id", how="left")
    cur = feats[feats.game_id.isin(up.game_id)].copy()
    train = feats[~feats.game_id.isin(up.game_id) & (feats.min_games_season >= 5)
                  & (feats.total != feats.line)]

    fm = fit_model(train, FEATURE_SETS[m["feature_set"]], m["learner"])
    cur["mu_resid"] = fm.predict_mean(cur)
    cur["sd"] = fm.resid_sd
    cur["proj_total"] = cur.line + cur.mu_resid
    cur["p_raw"], cur["p_push"] = over_probability(cur.mu_resid.values, cur.line.values, fm.resid_sd)

    # calibrator: walk-forward OOS predictions made before this date
    wf = pd.read_parquet(ROOT / "data" / "processed" / "predictions_locked.parquet")
    wf = wf[(wf.date < date) & wf.eligible_data & ~wf.push]
    cal = Calibrator(m["calib"]).fit(wf.p_raw.values, wf.over.values)
    cur["p_cal"] = cal.transform(cur.p_raw.values)
    cons = Calibrator("none").fit(cal.transform(wf.p_raw.values), wf.over.values)
    cur["p_cons"] = cons.lower_bound(cur.p_cal.values, q=sel["conservative_quantile"])
    cur["calibrated"] = True
    cur["eligible_data"] = cur.min_games_season >= load_config()["features"]["min_games_for_eligibility"]
    cur["push"] = False

    rho = lock["dependence_dev"]["z_corr"]
    rho_lo = lock["dependence_dev"]["z_corr_ci"][0]
    sp = SelectionParams(joint_target=sel["joint_target"], individual_floor=sel["individual_floor"],
                         single_cons_min=sel["single_cons_min"], min_edge_points=sel["min_edge_points"],
                         rho_hat=rho, rho_lo=rho_lo)
    dec = decide_slate(cur, sp)

    # contributions for the "reason" lines: change in projected residual if a feature were typical
    feats_used = FEATURE_SETS[m["feature_set"]]
    med = train[feats_used].median()
    contrib = {}
    for f in feats_used:
        alt = cur.copy()
        alt[f] = med[f]
        contrib[f] = cur.mu_resid.values - fm.predict_mean(alt)
    cur = cur.assign(**{f"c_{f}": v for f, v in contrib.items()})
    return cur, dec, sp, cal, cons, fm


def max_playable_line(row, sp, cal, cons, fm, partner=None, step=0.5):
    """Highest line at which the pick still qualifies: standalone (single standard) or,
    with a partner, keeping the card's conservative joint >= target."""
    mu_total = row.proj_total
    best = None
    L = np.floor(row.line) - 10 + 0.5
    while L <= row.line + 15:
        p_raw, _ = over_probability(np.array([mu_total - L]), np.array([L]), fm.resid_sd)
        p_cal = cal.transform(p_raw)
        p_cons = cons.lower_bound(p_cal)[0]
        if partner is None:
            ok = p_cons >= sp.single_cons_min and p_cons * row.odds - 1 > 0
        else:
            ok = joint_probability(p_cons, partner.p_cons, sp.rho_lo) >= sp.joint_target
        if ok:
            best = L
        L += step
    return best
