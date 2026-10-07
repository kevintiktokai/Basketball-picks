"""Bet-level analysis: buckets, ROI, drawdown, streaks, bootstrap, Monte Carlo,
failure analysis. Shared by the development and holdout reports."""
from __future__ import annotations

import numpy as np
import pandas as pd

from calibration.calibrate import brier, ece, log_loss, wilson

ODDS = 1.909


def bet_profit(over: pd.Series, push: pd.Series, odds: float = ODDS) -> np.ndarray:
    return np.where(push, 0.0, np.where(over == 1, odds - 1.0, -1.0))


def bet_summary(bets: pd.DataFrame, odds: float = ODDS) -> dict:
    """Flat 1-unit Over bets. `bets` needs over, push, p_cal, proj_total, line."""
    if len(bets) == 0:
        return {"bets": 0}
    prof = bet_profit(bets.over, bets.push, odds)
    settled = ~bets.push.values
    w = int((bets.over.values[settled] == 1).sum())
    n = int(settled.sum())
    eq = np.cumsum(prof)
    lo, hi = wilson(w, n)
    return {
        "bets": int(len(bets)), "wins": w, "losses": n - w, "pushes": int(bets.push.sum()),
        "win_rate": w / n if n else np.nan, "win_ci95": (lo, hi),
        "avg_pred": float(bets.p_cal.mean()),
        "cal_err": (w / n - float(bets.p_cal[settled].mean())) if n else np.nan,
        "avg_edge_pts": float((bets.proj_total - bets.line).mean()),
        "roi": float(prof.sum() / len(bets)), "profit_units": float(prof.sum()),
        "max_drawdown": float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max()),
        "longest_losing_streak": longest_streak(prof < 0),
        "brier": brier(bets.p_cal[settled], bets.over[settled]) if n else np.nan,
        "log_loss": log_loss(bets.p_cal[settled], bets.over[settled]) if n else np.nan,
    }


def longest_streak(mask) -> int:
    best = cur = 0
    for m in np.asarray(mask):
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return int(best)


def bucket_table(df: pd.DataFrame, col: str, edges, labels=None) -> pd.DataFrame:
    rows = []
    for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        m = (df[col] >= lo) & (df[col] < hi)
        s = bet_summary(df[m])
        rows.append({"bucket": labels[i] if labels else f"[{lo}, {hi})", "n": s["bets"],
                     "pred": s.get("avg_pred"), "win": s.get("win_rate"),
                     "ci": s.get("win_ci95"), "roi": s.get("roi"),
                     "cal_err": s.get("cal_err")})
    return pd.DataFrame(rows)


def date_bootstrap_mean(values: pd.Series, dates: pd.Series, n_boot=1000, seed=0):
    rng = np.random.default_rng(seed)
    g = pd.DataFrame({"v": values.values, "d": dates.values}).groupby("d")["v"]
    sums, cnts = g.sum().values, g.count().values
    k = len(sums)
    out = []
    for _ in range(n_boot):
        i = rng.integers(0, k, k)
        out.append(sums[i].sum() / cnts[i].sum())
    return float(np.mean(out)), tuple(np.percentile(out, [2.5, 97.5]))


def paired_logloss_gain(p_model, p_base, y, dates, n_boot=1000, seed=0):
    """Mean per-bet log-loss improvement of model over base, date-clustered CI."""
    def ll(p):
        p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p))
    diff = pd.Series(ll(p_base) - ll(p_model))
    return date_bootstrap_mean(diff, pd.Series(np.asarray(dates)), n_boot, seed)


def monte_carlo_cards(card_results: np.ndarray, card_profits: np.ndarray, months: int = 6,
                      cards_per_month: int | None = None, n_sim: int = 5000, seed: int = 0) -> dict:
    """Resample historical card outcomes to estimate distribution of outcomes."""
    rng = np.random.default_rng(seed)
    if len(card_results) == 0:
        return {}
    cpm = cards_per_month or max(1, len(card_results) // max(1, months))
    tot, losing_month, dd = [], 0, []
    for _ in range(n_sim):
        i = rng.integers(0, len(card_results), cpm * months)
        pr = card_profits[i]
        tot.append(pr.sum() / len(pr))
        monthly = pr.reshape(months, cpm).sum(axis=1)
        losing_month += (monthly < 0).mean()
        eq = np.cumsum(pr)
        dd.append((np.maximum.accumulate(eq) - eq).max())
    return {"expected_roi": float(np.mean(tot)), "roi_p5_p95": tuple(np.percentile(tot, [5, 95])),
            "p_losing_month": losing_month / n_sim, "median_max_drawdown": float(np.median(dd)),
            "p95_max_drawdown": float(np.percentile(dd, 95))}


def monte_carlo_singles(profits: np.ndarray, n_sim=5000, horizon=200, seed=0) -> dict:
    rng = np.random.default_rng(seed)
    if len(profits) == 0:
        return {}
    roi, ten_loss, dd = [], 0, []
    for _ in range(n_sim):
        p = profits[rng.integers(0, len(profits), horizon)]
        roi.append(p.mean())
        ten_loss += longest_streak(p < 0) >= 10
        eq = np.cumsum(p)
        dd.append((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    return {"horizon_bets": horizon, "expected_roi": float(np.mean(roi)),
            "roi_p5_p95": tuple(np.percentile(roi, [5, 95])),
            "p_10_loss_streak": ten_loss / n_sim, "median_max_drawdown": float(np.median(dd))}


def failure_analysis(losers: pd.DataFrame, box: pd.DataFrame | None) -> pd.DataFrame:
    """Decompose each losing Over: total error, pace error, efficiency error, game state.

    Categories (mechanical, decided before looking at any loss):
      F game-state failure : final margin >= 20 (blowout)
      A model error        : |total error| > 1.5 * model SD and projection disagreed with market
      C variance           : everything else (miss within normal predictive spread)
      B/D/E/G               : bad data / market info / roster / feature failure — not
                             identifiable with available data (no injury or line-movement feeds)
    """
    rows = []
    bx = None
    if box is not None:
        bx = box.set_index(["box_game_id", "team"])
    for r in losers.itertuples(index=False):
        err = r.total - r.proj_total
        margin = abs(r.home_pts - r.away_pts)
        pace_err = eff_err = np.nan
        if bx is not None and not pd.isna(r.box_game_id) and not pd.isna(getattr(r, "box_exp_pace", np.nan)):
            try:
                h = bx.loc[(r.box_game_id, r.home)]
                actual_pace = h.poss * 48.0 / max(h.minutes, 48.0)
                pace_err = actual_pace - r.box_exp_pace
                eff_err = 100 * r.total / h.poss - 100 * r.proj_total / r.box_exp_pace
            except KeyError:
                pass
        if margin >= 20:
            cat = "F_game_state_blowout"
        elif abs(err) > 1.5 * r.sd:
            cat = "A_model_error"
        else:
            cat = "C_variance"
        rows.append({"game_id": r.game_id, "line": r.line, "proj_total": r.proj_total,
                     "p_cal": r.p_cal, "total": r.total, "error": err,
                     "pace_error_poss": pace_err, "efficiency_error_pts_per100": eff_err,
                     "final_margin": margin, "category": cat})
    return pd.DataFrame(rows)


def fmt_pct(x, d=1):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100*x:.{d}f}%"


def df_to_md(df: pd.DataFrame, floatfmt="{:.3f}") -> str:
    def f(v):
        if isinstance(v, float):
            return "—" if np.isnan(v) else floatfmt.format(v)
        if isinstance(v, tuple):
            return "–".join("—" if (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}" for x in v)
        return str(v)
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(f(r[c]) for c in cols) + " |")
    return "\n".join(lines)
