"""Two-leg European totals cards from real soft-book prices, valued against Pinnacle.

Shared by the optimiser (scripts/euro_optimize.py) and the one-time holdout/test scripts, so
the locked strategy is evaluated by exactly the code that selected it.

A *leg* is a soft-book price (1xBet, Betway, Unibet, bet365; half-point total, Over or Under)
in force at a decision time. Its EV uses Pinnacle's no-vig ladder at that same moment; its CLV
uses Pinnacle's closing ladder. A *card* is two legs from different games on the same date
(Europe/Madrid) with combined odds >= 2.5; per date the pair with the highest joint EV is
taken (optionally then the next best pair among the remaining games, and so on).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from features.euro_market import board_at, fair_curve, fair_p

SOFT = ["1xbet", "betway", "unibet", "bet365"]
TZ = "Europe/Madrid"
MIN_ODDS = 2.5
SIGMA_MODEL = 17.0


def decision_times(T: pd.DataFrame, which: str) -> pd.Series:
    """Per fixture: when the bettor acts."""
    start = T.groupby("fixture_id").start.first()
    if which == "pinnacle_open":
        return T[T.book == "pinnacle"].groupby("fixture_id").t.min() + pd.Timedelta(milliseconds=1)
    if which == "game_day_10am":
        local = start.dt.tz_convert(TZ)
        ten = (local.dt.normalize() + pd.Timedelta(hours=10)).dt.tz_convert("UTC")
        return ten[ten < start]
    hours = int(which.rstrip("h"))
    return start - pd.Timedelta(hours=hours)


def legs(T: pd.DataFrame, when: pd.Series, CC: pd.DataFrame, final: pd.Series | None,
         model: pd.Series | None = None) -> pd.DataFrame:
    """Every soft-book leg in force at `when`, with EV now, CLV at the close, the model's view
    and (when `final` is given) the result."""
    B = board_at(T, when)
    C = fair_curve(B)
    S = B[B.book.isin(SOFT) & ((B.line * 2) % 2 == 1)].copy()
    S = S[S.fixture_id.isin(C.fixture_id) & S.fixture_id.isin(CC.fixture_id)]
    S["p_now"] = fair_p(C, S.fixture_id, S.line, S.side)
    S["ev_now"] = S.p_now * S.price - 1
    S["clv"] = fair_p(CC, S.fixture_id, S.line, S.side) * S.price - 1
    S["date"] = S.start.dt.tz_convert(TZ).dt.date
    mu = S.fixture_id.map(C.set_index("fixture_id").fair_mu)
    if model is not None:
        # model's disagreement with Pinnacle's fair line, centred on earlier dates (no look-ahead)
        g = pd.DataFrame({"fixture_id": S.fixture_id, "date": S.date, "dev": S.fixture_id.map(model) - mu})
        per = g.drop_duplicates("fixture_id").dropna()
        daily = per.groupby("date").dev.agg(["sum", "size"])
        prior = (daily["sum"].cumsum() - daily["sum"]) / (daily["size"].cumsum() - daily["size"]).replace(0, np.nan)
        dev = g.dev - g.date.map(prior).fillna(0.0)
        S["model_agrees"] = np.where(S.side == "over", dev > 0, dev < 0) & dev.notna()
    else:
        S["model_agrees"] = False
    if final is not None:
        tot = S.fixture_id.map(final)
        S = S[tot.notna().values].copy()
        tot = tot[tot.notna()]
        S["win"] = np.where(S.side == "over", tot.values > S.line.values, tot.values < S.line.values)
    return S.reset_index(drop=True)


def cards(L: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Cards per date under one strategy. cfg keys: leg_ev_min, leg_odds_band, books,
    model_agrees, cards_per_date ('1' or 'all_disjoint')."""
    books = SOFT if cfg["books"] == "all_soft" else [cfg["books"]]
    lo, hi = cfg["leg_odds_band"]
    E = L[L.book.isin(books) & (L.ev_now > cfg["leg_ev_min"]) & L.price.between(lo, hi)]
    if cfg.get("model_agrees"):
        E = E[E.model_agrees]
    if E.empty:
        return pd.DataFrame()
    E = E.sort_values("ev_now").groupby("fixture_id").tail(1)               # best leg per game
    out = []
    for d, g in E.groupby("date"):
        g = g.reset_index(drop=True)
        price, ev = g.price.values, g.ev_now.values
        n = len(g)
        if n < 2:
            continue
        i, j = np.triu_indices(n, 1)
        ok = price[i] * price[j] >= MIN_ODDS
        i, j = i[ok], j[ok]
        jev = (1 + ev[i]) * (1 + ev[j]) - 1
        order = np.argsort(-jev)
        used = set()
        for k in order:
            if jev[k] <= 0:
                break
            a, b = int(i[k]), int(j[k])
            if a in used or b in used:
                continue
            A, Bl = g.iloc[a], g.iloc[b]
            rec = {"date": d, "game_a": A.fixture_id, "game_b": Bl.fixture_id,
                   "leg_a": f"{A.book} {A.side} {A.line} @{A.price:.2f}",
                   "leg_b": f"{Bl.book} {Bl.side} {Bl.line} @{Bl.price:.2f}",
                   "odds": A.price * Bl.price, "ev": jev[k], "clv": (1 + A.clv) * (1 + Bl.clv) - 1}
            if "win" in g:
                rec["win"] = bool(A.win and Bl.win)
                rec["pnl"] = rec["odds"] - 1 if rec["win"] else -1.0
            out.append(rec)
            used |= {a, b}
            if cfg["cards_per_date"] == "1":
                break
    return pd.DataFrame(out)


def summary(C: pd.DataFrame, n_boot: int = 0, seed: int = 3) -> dict:
    if C.empty:
        return {"cards": 0}
    s = {"cards": len(C), "dates": C.date.nunique(), "mean odds": C.odds.mean(), "mean EV": C.ev.mean(),
         "mean CLV": C.clv.mean(), "CLV > 0": (C.clv > 0).mean()}
    if "win" in C:
        pnl = C.pnl.values
        cum = np.cumsum(pnl)
        runs, cur = 0, 0
        for x in pnl:
            cur = cur + 1 if x < 0 else 0
            runs = max(runs, cur)
        s.update({"both won": C.win.mean(), "break-even": (1 / C.odds).mean(), "ROI": pnl.mean(),
                  "profit (units)": pnl.sum(), "max drawdown": float(np.max(np.maximum.accumulate(
                      np.concatenate([[0], cum])) - np.concatenate([[0], cum]))), "longest losing run": runs})
        if n_boot:
            rng = np.random.default_rng(seed)
            by = C.groupby("date").pnl.agg(["sum", "size"])
            idx = rng.integers(0, len(by), (n_boot, len(by)))
            sims = by["sum"].values[idx].sum(1) / by["size"].values[idx].sum(1)
            s["ROI 95% CI"] = (np.percentile(sims, 2.5), np.percentile(sims, 97.5))
    return s
