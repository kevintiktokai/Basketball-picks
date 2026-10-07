"""Distributional total models: per-game MEAN and per-game SPREAD of the
residual r = outcome - line, plus PIT recalibration so that the probability of
ANY threshold (main line, buffered/alternate lines, Over or Under) is honest.

  mean model     : ridge / LightGBM / ensemble on market-specific features
  variance model : ridge on log(r_hat_resid^2) (heteroskedastic SD per game)
  shape          : 'normal', 'student_t' (fat tails, df fitted), or
                   'empirical' (standardized training residuals)
  recalibration  : PIT (probability integral transform) — fit G = CDF of the
                   model's own CDF values on earlier seasons' out-of-sample
                   predictions; calibrated P(Y <= y) = G(F(y)).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


@dataclass
class DistModel:
    mean_feats: list
    var_feats: list
    kind: str = "ridge"
    shape: str = "normal"
    alpha: float = 50.0
    med_: pd.Series = None
    mean_m: object = None
    mean_sc: object = None
    var_m: object = None
    var_sc: object = None
    base_sd: float = 1.0
    t_df: float = 30.0
    z_train: np.ndarray = field(default=None, repr=False)

    # ---------------------------------------------------------------- fit
    def fit(self, d: pd.DataFrame, seed: int = 0, weights: np.ndarray | None = None) -> "DistModel":
        self._w = None if weights is None else np.asarray(weights, float)
        y = d.resid.values.astype(float)
        allf = list(dict.fromkeys(self.mean_feats + self.var_feats))
        self.med_ = d[allf].median() if allf else pd.Series(dtype=float)
        mu = self._fit_mean(d, y, seed)
        res = y - mu
        self.base_sd = float(np.std(res))
        sd = self._fit_var(d, res)
        z = res / sd
        self.z_train = np.sort(z)
        if self.shape == "student_t":
            df, _, _ = stats.t.fit(z, floc=0, fscale=1)
            self.t_df = float(np.clip(df, 3, 200))
        return self

    def _X(self, d, feats):
        return d[feats].fillna(self.med_[feats])

    def _fit_mean(self, d, y, seed):
        if not self.mean_feats:
            self.mean_m = float(np.mean(y))
            return np.full(len(y), self.mean_m)
        X = self._X(d, self.mean_feats)
        if self.kind == "ridge":
            self.mean_sc = StandardScaler().fit(X)
            self.mean_m = Ridge(alpha=self.alpha).fit(self.mean_sc.transform(X), y, sample_weight=self._w)
        elif self.kind == "lgbm":
            import lightgbm as lgb
            self.mean_m = lgb.LGBMRegressor(
                n_estimators=400, learning_rate=0.02, num_leaves=15, min_child_samples=300,
                subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=20.0,
                random_state=seed, verbose=-1).fit(X, y)
        elif self.kind == "ensemble":
            self.mean_sc = StandardScaler().fit(X)
            r = Ridge(alpha=self.alpha).fit(self.mean_sc.transform(X), y)
            import lightgbm as lgb
            l = lgb.LGBMRegressor(
                n_estimators=400, learning_rate=0.02, num_leaves=15, min_child_samples=300,
                subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=20.0,
                random_state=seed, verbose=-1).fit(X, y)
            self.mean_m = (r, l)
        return self.predict_mean(d)

    def predict_mean(self, d) -> np.ndarray:
        if not self.mean_feats:
            return np.full(len(d), self.mean_m)
        X = self._X(d, self.mean_feats)
        if self.kind == "ridge":
            return self.mean_m.predict(self.mean_sc.transform(X))
        if self.kind == "lgbm":
            return self.mean_m.predict(X)
        r, l = self.mean_m
        return 0.5 * (r.predict(self.mean_sc.transform(X)) + l.predict(X))

    def _fit_var(self, d, res):
        if not self.var_feats:
            self.var_m = None
            return np.full(len(res), self.base_sd)
        X = self._X(d, self.var_feats)
        self.var_sc = StandardScaler().fit(X)
        target = np.log(res ** 2 + 1.0)
        self.var_m = Ridge(alpha=self.alpha).fit(self.var_sc.transform(X), target,
                                                 sample_weight=getattr(self, "_w", None))
        raw = np.exp(self.var_m.predict(self.var_sc.transform(X)))
        # rescale so that mean squared standardized residual = 1
        self.var_scale = float(np.sqrt(np.mean(res ** 2 / raw)))
        return np.sqrt(raw) * self.var_scale

    def predict_sd(self, d) -> np.ndarray:
        if self.var_m is None:
            return np.full(len(d), self.base_sd)
        X = self._X(d, self.var_feats)
        raw = np.exp(self.var_m.predict(self.var_sc.transform(X)))
        return np.sqrt(raw) * self.var_scale

    # --------------------------------------------------------- distribution
    def cdf_z(self, z: np.ndarray) -> np.ndarray:
        """CDF of the standardized residual."""
        if self.shape == "normal":
            return stats.norm.cdf(z)
        if self.shape == "student_t":
            # unit-variance t
            s = np.sqrt(self.t_df / (self.t_df - 2)) if self.t_df > 2 else 1.0
            return stats.t.cdf(z * s, self.t_df)
        if self.shape == "empirical":
            return np.searchsorted(self.z_train, z, side="right") / len(self.z_train)
        raise ValueError(self.shape)


# ------------------------------------------------------------------ PIT calibration
class PITCalibrator:
    """Calibrated CDF: G(u) where u = model CDF value. G is the (smoothed)
    empirical CDF of u on historical out-of-sample predictions."""

    def __init__(self, n_knots: int = 200):
        self.n_knots = n_knots

    def fit(self, u: np.ndarray) -> "PITCalibrator":
        u = np.sort(np.clip(np.asarray(u, float), 0, 1))
        self.u = u
        self.n = len(u)
        q = np.linspace(0, 1, self.n_knots + 1)
        self.knots_x = np.quantile(u, q)
        self.knots_y = q
        # ensure strictly increasing x for interpolation
        self.knots_x, idx = np.unique(self.knots_x, return_index=True)
        self.knots_y = self.knots_y[idx]
        return self

    def G(self, u: np.ndarray) -> np.ndarray:
        return np.interp(np.clip(u, 0, 1), np.r_[0, self.knots_x, 1], np.r_[0, self.knots_y, 1])

    def G_bounds(self, u: np.ndarray, q: float = 0.05):
        """One-sided Beta bounds on G(u): count of historical u' <= u."""
        k = np.searchsorted(self.u, np.clip(u, 0, 1), side="right")
        lo = stats.beta.ppf(q, k + 0.5, self.n - k + 0.5)       # lower bound on P(Y<=y)
        hi = stats.beta.ppf(1 - q, k + 0.5, self.n - k + 0.5)   # upper bound
        return lo, hi


def threshold_probs(model: DistModel, cal: PITCalibrator | None, mu: np.ndarray, sd: np.ndarray,
                    line: np.ndarray, threshold: np.ndarray, q: float = 0.05):
    """For integer outcomes: P(outcome > threshold) and P(outcome < threshold) with
    continuity correction, calibrated and conservative (lower bounds).
    `line` is the market line the residual model is defined against; threshold may
    differ from line (buffered/alternate lines)."""
    thr = np.asarray(threshold, float)
    over_edge = np.floor(thr) + 0.5          # outcome >= floor(thr)+1  <=> over wins
    under_edge = np.ceil(thr) - 0.5          # outcome <= ceil(thr)-1   <=> under wins
    z_over = (over_edge - line - mu) / sd
    z_under = (under_edge - line - mu) / sd
    u_over = model.cdf_z(z_over)             # P(Y <= over_edge) = P(over loses or pushes)
    u_under = model.cdf_z(z_under)           # P(Y <= under_edge) = P(under wins)
    if cal is None:
        p_over = 1 - u_over
        p_under = u_under
        return p_over, p_under, p_over, p_under
    g_over = cal.G(u_over)
    g_under = cal.G(u_under)
    lo_o, hi_o = cal.G_bounds(u_over, q)
    lo_u, hi_u = cal.G_bounds(u_under, q)
    p_over = 1 - g_over
    p_under = g_under
    cons_over = 1 - hi_o                     # pessimistic for the Over
    cons_under = lo_u                        # pessimistic for the Under
    return p_over, p_under, cons_over, cons_under


# ------------------------------------------------- latent (edge-aware) calibration
class LatentCalibrator:
    """P(win) = sigmoid(b0 + b1*s_model + b2*s_buf + b3*s_buf^2 + b4*s_model*s_buf)
    where, for a bet on side (+1 Over, -1 Under) at threshold t:
        s_model = side * mu / sd           (model's standardized disagreement with the line)
        s_buf   = side * (line - t') / sd   (standardized buffer bought; t' on the half-point grid)
    Fitted on pseudo-bets at many buffers over EARLIER seasons' out-of-sample predictions.
    Conservative probability: one-sided lower bound of the linear predictor using a
    date-clustered (sandwich) covariance — widens automatically when extrapolating."""

    BUFFERS = np.array([-6, -3, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18], float)

    @staticmethod
    def design(s_model, s_buf):
        s_model = np.asarray(s_model, float)
        s_buf = np.asarray(s_buf, float)
        return np.column_stack([np.ones_like(s_model), s_model, s_buf, s_buf ** 2, s_model * s_buf])

    @classmethod
    def pseudo_bets(cls, hist: pd.DataFrame) -> pd.DataFrame:
        """hist needs: date, line, outcome, mu, sd."""
        rows = []
        base = np.floor(hist.line.values) + 0.5           # half-point grid -> no pushes
        for side in (1, -1):
            for k in cls.BUFFERS:
                thr = base - side * k                     # Over: lower line; Under: higher line
                win = (hist.outcome.values > thr) if side == 1 else (hist.outcome.values < thr)
                rows.append(pd.DataFrame({
                    "date": hist.date.values,
                    "s_model": side * hist.mu.values / hist.sd.values,
                    "s_buf": side * (hist.line.values - thr) / hist.sd.values,
                    "win": win.astype(int)}))
        return pd.concat(rows, ignore_index=True)

    def fit(self, hist: pd.DataFrame, weights: np.ndarray | None = None) -> "LatentCalibrator":
        pb = self.pseudo_bets(hist)
        X = self.design(pb.s_model, pb.s_buf)
        y = pb.win.values.astype(float)
        sw = np.ones(len(pb)) if weights is None else np.tile(np.asarray(weights, float),
                                                             len(pb) // len(hist))
        beta = np.zeros(X.shape[1])
        for _ in range(50):                                  # Newton-Raphson logistic fit
            eta = X @ beta
            p = 1 / (1 + np.exp(-eta))
            W = sw * p * (1 - p)
            H = (X * W[:, None]).T @ X + 1e-6 * np.eye(X.shape[1])
            step = np.linalg.solve(H, X.T @ (sw * (y - p)))
            beta += step
            if np.max(np.abs(step)) < 1e-8:
                break
        p = 1 / (1 + np.exp(-(X @ beta)))
        H = (X * (sw * p * (1 - p))[:, None]).T @ X
        Hinv = np.linalg.inv(H)
        score = X * (sw * (y - p))[:, None]
        g = pd.DataFrame(score).groupby(pb.date.values).sum().values   # cluster by date
        meat = g.T @ g
        self.beta = beta
        self.V = Hinv @ meat @ Hinv
        self.n_pseudo = len(pb)
        return self

    def prob(self, s_model, s_buf, z: float | None = None):
        X = self.design(s_model, s_buf)
        eta = X @ self.beta
        p = 1 / (1 + np.exp(-eta))
        if z is None:
            return p
        se = np.sqrt(np.einsum("ij,jk,ik->i", X, self.V, X))
        return p, 1 / (1 + np.exp(-(eta - z * se)))
