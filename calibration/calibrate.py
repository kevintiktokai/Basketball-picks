"""Probability calibration and calibration diagnostics.

Calibrators are only ever fitted on walk-forward out-of-sample predictions from
seasons strictly before the season being calibrated.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


class Calibrator:
    """method in {'none', 'platt', 'isotonic'}; also exposes a conservative
    lower bound for any calibrated probability via a Beta posterior on the
    historical win rate of bets in the same predicted-probability neighbourhood."""

    def __init__(self, method: str = "platt", bin_width: float = 0.02):
        self.method = method
        self.bin_width = bin_width

    def fit(self, p_raw: np.ndarray, y: np.ndarray) -> "Calibrator":
        p_raw = np.asarray(p_raw, float)
        y = np.asarray(y, float)
        if self.method == "platt":
            self.m = LogisticRegression(C=1.0).fit(_logit(p_raw).reshape(-1, 1), y)
        elif self.method == "isotonic":
            self.m = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99).fit(p_raw, y)
        self.hist_p = p_raw
        self.hist_y = y
        return self

    def transform(self, p_raw: np.ndarray) -> np.ndarray:
        p_raw = np.asarray(p_raw, float)
        if self.method == "none":
            return p_raw
        if self.method == "platt":
            return self.m.predict_proba(_logit(p_raw).reshape(-1, 1))[:, 1]
        return self.m.predict(p_raw)

    def lower_bound(self, p_raw: np.ndarray, q: float = 0.05, min_n: int = 30) -> np.ndarray:
        """Conservative probability: q-quantile of Beta(1+wins, 1+losses) over
        historical bets whose raw probability was >= this one's lower edge
        (one-sided neighbourhood, so thin tails borrow from the bulk below them,
        which is deliberately pessimistic). Returns 0.5-ish when unsupported."""
        p_raw = np.asarray(p_raw, float)
        order = np.argsort(self.hist_p)
        hp = self.hist_p[order]
        hy = self.hist_y[order]
        cum_w = np.cumsum(hy[::-1])[::-1]         # wins among bets with p >= hp[i]
        out = np.empty_like(p_raw)
        for i, p in enumerate(p_raw):
            lo = np.searchsorted(hp, p - self.bin_width, side="left")
            hi = np.searchsorted(hp, p + self.bin_width, side="right")
            n = hi - lo
            if n < min_n:                          # widen downward until supported
                lo = max(0, hi - min_n)
                n = hi - lo
            if n == 0:
                out[i] = 0.0
                continue
            w = hy[lo:hi].sum()
            out[i] = stats.beta.ppf(q, 1 + w, 1 + n - w)
        return out


# ------------------------------------------------------------------ metrics
def brier(p, y):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def log_loss(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def ece(p, y, bins=10):
    p = np.asarray(p, float)
    y = np.asarray(y, float)
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
    e = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(e)


def reliability_table(p, y, edges=(0, .50, .55, .60, .65, .70, .75, 1.0001)) -> pd.DataFrame:
    p = np.asarray(p, float)
    y = np.asarray(y, float)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi)
        n = int(m.sum())
        if n == 0:
            rows.append({"bucket": f"{lo:.0%}-{min(hi,1):.0%}", "n": 0})
            continue
        w = y[m].mean()
        ci = wilson(int(y[m].sum()), n)
        rows.append({"bucket": f"{lo:.0%}-{min(hi,1):.0%}", "n": n, "pred": p[m].mean(),
                     "actual": w, "ci_lo": ci[0], "ci_hi": ci[1], "cal_err": w - p[m].mean()})
    return pd.DataFrame(rows)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)
