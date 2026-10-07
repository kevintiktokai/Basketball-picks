"""Expected-total / Over-probability models.

All models predict the RESIDUAL r = final_total - bookmaker_line, i.e. how wrong
the line is expected to be, plus a predictive distribution for r. The Over
probability is P(total > line) derived from that distribution, never from a
point projection.

Ablation ladder (feature sets are cumulative):
  F0 market_only   : nothing beyond the line (predicts the trailing mean residual)
  F1 naive_ppg     : raw recent PPG for/against (the old manual approach)
  F2 ratings       : opponent-adjusted scoring ratings
  F3 pace_eff      : possessions x efficiency expected total (box seasons only)
  F4 matchup       : four-factor offence-vs-defence interactions (box seasons only)
  F5 rest_home     : rest days, back-to-backs
  F6 market        : spread size (blowout risk), market team tendencies, league drift, line level
  F7 context       : season phase, games played, postseason
  F8 trends        : recent Over/Under trend of each team (the old "Over trend" heuristic)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["x_naive"] = d.naive_ppg_total - d.line
    d["x_rating"] = d.rating_exp_total - d.line
    d["x_box"] = d.box_exp_total - d.line
    d["x_pace_rel"] = d.box_exp_pace - d.groupby("season").box_exp_pace.transform(
        lambda s: s.expanding().mean().shift(1))
    # matchup: offence quality vs the opponent's matching defensive allowance
    for side, opp in (("home", "away"), ("away", "home")):
        d[f"m_{side}_efg"] = d[f"{side}_efg"] + d[f"{opp}_efg_allowed"]
        d[f"m_{side}_3par"] = d[f"{side}_tpar"] + d[f"{opp}_tpar_allowed"]
        d[f"m_{side}_ftr"] = d[f"{side}_ftr"] + d[f"{opp}_ftr_allowed"]
        d[f"m_{side}_orb"] = d[f"{side}_orb"] + d[f"{opp}_orb_allowed"]
        d[f"m_{side}_tov"] = d[f"{side}_tov"] + d[f"{opp}_tov_forced"]
    d["m_efg"] = d.m_home_efg + d.m_away_efg
    d["m_3par"] = d.m_home_3par + d.m_away_3par
    d["m_ftr"] = d.m_home_ftr + d.m_away_ftr
    d["m_orb"] = d.m_home_orb + d.m_away_orb
    d["m_tov"] = d.m_home_tov + d.m_away_tov
    d["abs_spread"] = d.home_spread.abs()
    d["rest_sum"] = d.home_rest + d.away_rest
    d["b2b_any"] = d.home_b2b + d.away_b2b
    d["line_tend_sum"] = d.home_line_tend + d.away_line_tend
    d["ou_trend_sum"] = d.home_ou_trend + d.away_ou_trend
    d["line_rel"] = d.line - d.lg_line_trailing
    d["early_season"] = (d.min_games_season < 10).astype(int)
    d["postseason"] = d.is_postseason.astype(int)
    d["log_games"] = np.log1p(d.min_games_season)
    return d


FEATURE_SETS: dict[str, list[str]] = {}
_ladder = [
    ("F0_market_only", []),
    ("F1_naive_ppg", ["x_naive"]),
    ("F2_ratings", ["x_rating"]),
    ("F3_pace_eff", ["x_box", "x_pace_rel"]),
    ("F4_matchup", ["m_efg", "m_3par", "m_ftr", "m_orb", "m_tov"]),
    ("F5_rest_home", ["rest_sum", "b2b_any"]),
    ("F6_market", ["abs_spread", "line_tend_sum", "lg_total_minus_line", "line_rel"]),
    ("F7_context", ["early_season", "postseason", "log_games"]),
    ("F8_trends", ["ou_trend_sum"]),
]
_acc: list[str] = []
for _name, _cols in _ladder:
    _acc = _acc + _cols
    FEATURE_SETS[_name] = list(_acc)
BOX_FEATURES = {"x_box", "x_pace_rel", "m_efg", "m_3par", "m_ftr", "m_orb", "m_tov"}

# score-only variant of the full model (usable in every season, incl. live-sim)
FEATURE_SETS["S_scores_full"] = [c for c in FEATURE_SETS["F8_trends"] if c not in BOX_FEATURES]
FEATURE_SETS["S_scores_core"] = ["x_rating", "abs_spread", "lg_total_minus_line", "line_rel",
                                 "early_season", "postseason"]


def needs_box(feature_set: str) -> bool:
    return bool(set(FEATURE_SETS[feature_set]) & BOX_FEATURES)


# ----------------------------------------------------------------- learners
@dataclass
class FittedModel:
    kind: str
    features: list
    mean_fn: object
    resid_sd: float
    resid_sample: np.ndarray        # training residuals of the model (for empirical dist.)

    def predict_mean(self, X: pd.DataFrame) -> np.ndarray:
        return self.mean_fn(X)


def _fill(X: pd.DataFrame, med: pd.Series) -> pd.DataFrame:
    return X.fillna(med)


def fit_model(train: pd.DataFrame, features: list[str], kind: str, seed: int = 0) -> FittedModel:
    y = (train.total - train.line).values.astype(float)
    if not features or kind == "mean":
        mu = float(np.mean(y))
        fn = lambda X, mu=mu: np.full(len(X), mu)
        res = y - mu
        return FittedModel("mean", [], fn, float(np.std(res)), res)

    X = train[features]
    med = X.median()
    Xf = _fill(X, med)
    if kind == "ridge":
        sc = StandardScaler().fit(Xf)
        m = Ridge(alpha=50.0).fit(sc.transform(Xf), y)
        fn = lambda X, m=m, sc=sc, med=med: m.predict(sc.transform(_fill(X[features], med)))
    elif kind == "lgbm":
        import lightgbm as lgb
        m = lgb.LGBMRegressor(
            n_estimators=300, learning_rate=0.02, num_leaves=8, min_child_samples=200,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=10.0,
            random_state=seed, verbose=-1,
        ).fit(Xf, y)
        fn = lambda X, m=m, med=med: m.predict(_fill(X[features], med))
    elif kind == "ensemble":
        a = fit_model(train, features, "ridge", seed)
        b = fit_model(train, features, "lgbm", seed)
        fn = lambda X, a=a, b=b: 0.5 * (a.predict_mean(X) + b.predict_mean(X))
    else:
        raise ValueError(kind)
    res = y - fn(train)
    return FittedModel(kind, features, fn, float(np.std(res)), res)


# ------------------------------------------------------- over probability
def over_probability(mu_resid: np.ndarray, line: np.ndarray, sd: float,
                     dist: str = "normal", resid_sample: np.ndarray | None = None):
    """Return (P(over | no push), P(push)) for integer final totals.

    Over wins iff total >= floor(line) + 1. A whole-number line can push.
    """
    line = np.asarray(line, dtype=float)
    mean_total = line + mu_resid
    over_thr = np.floor(line) + 0.5          # continuity-corrected boundary
    whole = (line == np.floor(line))
    if dist == "normal":
        p_over = 1.0 - stats.norm.cdf((over_thr - mean_total) / sd)
        p_push = np.where(
            whole,
            stats.norm.cdf((line + 0.5 - mean_total) / sd) - stats.norm.cdf((line - 0.5 - mean_total) / sd),
            0.0,
        )
    elif dist == "empirical":
        rs = np.sort(resid_sample)
        n = len(rs)
        # P(total > thr) = P(resid_model > thr - mean_total)
        z = over_thr - mean_total
        p_over = 1.0 - np.searchsorted(rs, z, side="right") / n
        lo = np.searchsorted(rs, line - 0.5 - mean_total, side="right") / n
        hi = np.searchsorted(rs, line + 0.5 - mean_total, side="right") / n
        p_push = np.where(whole, hi - lo, 0.0)
    else:
        raise ValueError(dist)
    p_over_np = p_over / np.clip(1.0 - p_push, 1e-9, None)
    return np.clip(p_over_np, 1e-4, 1 - 1e-4), p_push


def line_probabilities(mu_total: float, sd: float, lines: list[float]) -> dict[float, float]:
    """P(Over | no push) at each candidate line — used by the line-sensitivity module."""
    out = {}
    for L in lines:
        p, _ = over_probability(np.array([mu_total - L]), np.array([L]), sd)
        out[L] = float(p[0])
    return out
