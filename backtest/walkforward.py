"""Walk-forward prediction engine.

For each test season s (in order), a model is fitted on all seasons < s and
used to predict every game of season s; features are themselves point-in-time
(see features/pit.py). A calibrator for season s is fitted only on the
out-of-sample raw predictions of seasons < s. Nothing from season s or later
reaches any fitted object used for season s.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from calibration.calibrate import Calibrator
from config_loader import ROOT, load_config
from models.total_models import (FEATURE_SETS, add_derived, fit_model, needs_box,
                                 over_probability)

ALL_SEASONS = [f"{y}-{str(y + 1)[2:]}" for y in range(2007, 2026)]
BOX_SEASONS = [f"{y}-{str(y + 1)[2:]}" for y in range(2010, 2024)]


def load_features() -> pd.DataFrame:
    path = ROOT / "data" / "processed" / "features.parquet"
    if not path.exists():
        from features.pit import build_features
        g = pd.read_parquet(ROOT / "data" / "processed" / "games.parquet")
        b = pd.read_parquet(ROOT / "data" / "processed" / "team_box.parquet")
        build_features(g, b).to_parquet(path, index=False)
    df = add_derived(pd.read_parquet(path))
    df["resid"] = df.total - df.line
    df["push"] = (df.total == df.line)
    df["over"] = (df.total > df.line).astype(int)
    return df


def allowed_seasons(stage: str) -> list[str]:
    """Seasons whose games may be PREDICTED at a given research stage."""
    p = load_config()["periods"]
    if stage == "development":
        return p["discovery"] + p["validation"]
    if stage == "holdout":
        return p["discovery"] + p["validation"] + p["holdout"]
    if stage == "live_sim":
        return p["discovery"] + p["validation"] + p["holdout"] + p["live_sim"]
    raise ValueError(stage)


def walk_forward(df: pd.DataFrame, feature_set: str, kind: str, dist: str = "normal",
                 calib: str = "platt", stage: str = "development",
                 min_games: int | None = None) -> pd.DataFrame:
    cfg = load_config()
    min_games = cfg["features"]["min_games_for_eligibility"] if min_games is None else min_games
    feats = FEATURE_SETS[feature_set]
    seasons = [s for s in ALL_SEASONS if s in allowed_seasons(stage)]
    if needs_box(feature_set):
        seasons = [s for s in seasons if s in BOX_SEASONS]
    data = df[df.season.isin(seasons)]
    trainable = data[(data.min_games_season >= min_games)]

    out = []
    min_train = cfg["walk_forward"]["min_train_seasons"]
    for i, s in enumerate(seasons):
        if i < min_train:
            continue
        tr = trainable[trainable.season.isin(seasons[:i]) & ~trainable.push]
        te = data[data.season == s].copy()
        m = fit_model(tr, feats, kind)
        te["mu_resid"] = m.predict_mean(te)
        te["sd"] = m.resid_sd
        p, pp = over_probability(te.mu_resid.values, te.line.values, m.resid_sd, dist, m.resid_sample)
        te["p_raw"] = p
        te["p_push"] = pp
        te["proj_total"] = te.line + te.mu_resid
        out.append(te)
    pred = pd.concat(out, ignore_index=True)
    pred["eligible_data"] = pred.min_games_season >= min_games

    # walk-forward calibration (calibrator for s sees only predictions of seasons < s)
    pred["p_cal"] = np.nan
    pred["p_cons"] = np.nan
    pred_seasons = list(dict.fromkeys(pred.season))
    for j, s in enumerate(pred_seasons):
        hist = pred[pred.season.isin(pred_seasons[:j]) & pred.eligible_data & ~pred.push]
        idx = pred.season == s
        if j < 2 or len(hist) < 1000:
            continue  # not enough OOS history to calibrate: season used as calibration seed only
        c = Calibrator(calib).fit(hist.p_raw.values, hist.over.values)
        pred.loc[idx, "p_cal"] = c.transform(pred.loc[idx, "p_raw"].values)
        # conservative bound computed on the calibrated scale of the history
        hist_cal = c.transform(hist.p_raw.values)
        cons = Calibrator("none").fit(hist_cal, hist.over.values)
        q = cfg["selection"]["conservative_quantile"]
        pred.loc[idx, "p_cons"] = cons.lower_bound(pred.loc[idx, "p_cal"].values, q=q)
    pred["calibrated"] = pred.p_cal.notna()
    pred["feature_set"] = feature_set
    pred["model_kind"] = kind
    pred["dist"] = dist
    pred["calib"] = calib
    return pred
