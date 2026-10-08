"""Europe development study (config/europe.yaml), Q1 and Q2: soft-book totals against Pinnacle.

Development games only: 2025-26 from 2026-01-20. The 2026-27 games are the test set; they are
dropped before anything is computed and are never joined to results here.

Q1  Opening lines. At the first moment both are posted, each soft book's main line against
    Pinnacle's no-vig line, and the closing-line value of betting it toward Pinnacle.
Q2  Value prices. Soft-book prices (any ladder line, either side) above Pinnacle's no-vig
    probability at the same moment, at three decision times: when Pinnacle opens, and 6 h
    and 1 h before tip-off. Reported: expected value at that moment, closing-line value
    against Pinnacle's close (the low-noise signal), and actual results (secondary).
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from backtest.analysis import df_to_md
from config_loader import ROOT, log_experiment
from data import oddspapi as op
from data.euroleague import parse as euro_parse
from features.euro_market import board_at, close_board, fair_curve, fair_p, timelines, two_way

DEV_FROM, DEV_TO = pd.Timestamp("2026-01-20", tz="UTC"), pd.Timestamp("2026-07-01", tz="UTC")
SOFT = ["1xbet", "betway", "unibet", "bet365"]
THRESH = [0.0, 0.02, 0.04]
BAND = (1.40, 1.90)                       # the card-leg odds band
rng = np.random.default_rng(7)


def results(T: pd.DataFrame) -> pd.Series:
    """Final total per fixture, from the official API, matched on date and team names."""
    G, _ = euro_parse(["E2025", "U2025"])
    F = T.groupby("fixture_id")[["start", "home_name", "away_name"]].first().reset_index()
    F = op.match_official(F, G)
    tot = G.set_index("game_key").total
    return F.set_index("fixture_id").game_key.map(tot), F


def boot_roi(df: pd.DataFrame, n: int = 2000):
    """ROI per 1-unit bet with a game-clustered bootstrap CI."""
    if df.empty:
        return np.nan, (np.nan, np.nan)
    g = df.groupby("fixture_id").agg(pnl=("pnl", "sum"), k=("pnl", "size"))
    pnl, k = g.pnl.values, g.k.values
    idx = rng.integers(0, len(g), (n, len(g)))
    sims = pnl[idx].sum(1) / k[idx].sum(1)
    return pnl.sum() / k.sum(), (np.percentile(sims, 2.5), np.percentile(sims, 97.5))


def legs_at(T, when, CC, final):
    """Soft-book legs in force at `when`, valued against Pinnacle's fair curve then and at close."""
    B = board_at(T, when)
    C = fair_curve(B)
    S = B[B.book.isin(SOFT) & ((B.line * 2) % 2 == 1)].copy()
    S = S[S.fixture_id.isin(C.fixture_id) & S.fixture_id.isin(CC.fixture_id)]
    S["p_now"] = fair_p(C, S.fixture_id, S.line, S.side)
    S["p_close"] = fair_p(CC, S.fixture_id, S.line, S.side)
    S["ev_now"] = S.p_now * S.price - 1
    S["clv"] = S.p_close * S.price - 1
    tot = S.fixture_id.map(final)
    S["win"] = np.where(S.side == "over", tot > S.line, tot < S.line)
    S["pnl"] = np.where(S.win, S.price - 1, -1.0)
    return S[tot.notna().values]


def q1(T, CC, final) -> pd.DataFrame:
    """At the first moment both are posted (Pinnacle open or the soft book's open, whichever is
    later): the soft book's main line against Pinnacle's no-vig line, betting toward Pinnacle."""
    first = T.groupby(["fixture_id", "book"]).t.min().unstack()
    rows = []
    for book in SOFT:
        if book not in first or "pinnacle" not in first:
            continue
        when = first[[book, "pinnacle"]].dropna().max(axis=1) + pd.Timedelta(milliseconds=1)
        B = board_at(T, when)
        C = fair_curve(B)
        w = two_way(B[B.book == book])
        w = w[(w.line * 2) % 2 == 1]
        if C.empty or w.empty:
            continue
        w["imb"] = (1 / w.over - 1 / w.under).abs()
        m = w.sort_values("imb").groupby("fixture_id").head(1)            # soft main line then
        m = m.merge(C[["fixture_id", "fair_mu"]], on="fixture_id").merge(
            CC[["fixture_id", "fair_mu"]].rename(columns={"fair_mu": "close_mu"}), on="fixture_id")
        m["gap"] = m.line - m.fair_mu                           # soft line above Pinnacle -> Under
        side = np.where(m.gap > 0, "under", "over")
        price = np.where(m.gap > 0, m.under, m.over)
        m["clv"] = fair_p(CC, m.fixture_id, m.line, side) * price - 1
        tot = m.fixture_id.map(final)
        win = np.where(side == "over", tot > m.line, tot < m.line)
        m["pnl"] = np.where(win, price - 1, -1.0)
        m = m[tot.notna().values]
        for k in (0.0, 1.0, 2.0, 3.0):
            s = m[m.gap.abs() >= k] if k else m
            roi, ci = boot_roi(s)
            rows.append({"soft book": book, "gap >= pts (abs)": k, "games": len(s),
                         "mean abs gap": s.gap.abs().mean(),
                         "close stays on Pinnacle's side": (np.sign(s.line - s.close_mu) == np.sign(s.gap)).mean(),
                         "mean CLV": s.clv.mean(), "won": (s.pnl > 0).mean(), "ROI": roi, "ROI 95% CI": ci})
    return pd.DataFrame(rows)


def q2(T, CC, final) -> pd.DataFrame:
    first_pin = T[T.book == "pinnacle"].groupby("fixture_id").t.min()
    start = T.groupby("fixture_id").start.first()
    times = {"when Pinnacle opens": first_pin,
             "6 h before tip": start - pd.Timedelta(hours=6),
             "1 h before tip": start - pd.Timedelta(hours=1)}
    rows = []
    for label, when in times.items():
        S = legs_at(T, when, CC, final)
        for thr in THRESH:
            for band in (False, True):
                s = S[S.ev_now > thr]
                if band:
                    s = s[s.price.between(*BAND)]
                best = s.sort_values("ev_now").groupby("fixture_id").tail(1)   # one bet per game
                roi, ci = boot_roi(best)
                rows.append({"decision time": label, "EV now >": thr, "odds 1.40-1.90 only": band,
                             "legs available": len(s), "games (1 bet each)": len(best),
                             "mean EV now": best.ev_now.mean(), "mean CLV": best.clv.mean(),
                             "CLV > 0": (best.clv > 0).mean(), "won": best.win.mean(),
                             "ROI": roi, "ROI 95% CI": ci})
    return pd.DataFrame(rows)


def main():
    T = timelines()
    T = T[(T.start >= DEV_FROM) & (T.start < DEV_TO)]
    T = T.drop_duplicates(["fixture_id", "book", "line", "side", "t"])
    final, F = results(T)
    CB = close_board(T)
    CC = fair_curve(CB)
    cover = T.groupby("book").fixture_id.nunique()
    A, B = q1(T, CC, final), q2(T, CC, final)
    lines = ["# Europe development study: soft books against Pinnacle (Q1, Q2)\n",
             f"Development games (2025-26, from 2026-01-20) with any pre-game totals: **{T.fixture_id.nunique()}**; "
             f"matched to official results: {int(final.notna().sum())}. Games per book: "
             + ", ".join(f"{b} {n}" for b, n in cover.items()) + ". Pinnacle closing fair line available for "
             f"{len(CC)} games.\n",
             "EV = probability x price - 1, with the probability from Pinnacle's no-vig ladder; "
             "**CLV** values the same bet against Pinnacle's *closing* ladder (positive = the market "
             "moved your way). One bet per game (the best EV), ROI per 1-unit bet with a game-"
             "clustered bootstrap CI.\n",
             "## Q1 — soft-book opening lines against Pinnacle\n",
             "At the first moment both are posted, bet the soft book's main line toward Pinnacle's "
             "fair line (Under if the soft line is higher). Gap = soft line - Pinnacle's fair line.\n",
             df_to_md(A, "{:.3f}"), "",
             "## Q2 — soft-book prices above Pinnacle's fair price\n", df_to_md(B, "{:.3f}"), ""]
    out = ROOT / "reports" / "euro_dev_q1q2.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("euro_dev_q1q2", {"dev": [str(DEV_FROM), str(DEV_TO)], "soft": SOFT, "thresh": THRESH,
                                     "band": BAND}, {"q1": A.to_dict("records"), "q2": B.to_dict("records"),
                                                     "games": int(T.fixture_id.nunique())})


if __name__ == "__main__":
    main()
