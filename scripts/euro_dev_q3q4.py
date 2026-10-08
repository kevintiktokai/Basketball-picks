"""Europe development study (config/europe.yaml), Q3 and Q4.

Development games only (2025-26 from 2026-01-20); 2026-27 is never joined to results here.

Q3  Does the rating model add information to Pinnacle's opening line? The low-noise test is
    whether Pinnacle's line moves from open to close toward the model's disagreement; also the
    correlation with the result, a log-loss check, and the closing-line value of betting the
    model's side at Pinnacle's opening price when it disagrees by >= k points.
Q4  Two-leg cards at combined odds >= 2.5 (legs 1.40-1.90) built only from REAL soft-book
    prices that beat Pinnacle's fair price at the decision time: per slate (date), the pair of
    games with the highest joint EV. Reported: joint EV, joint CLV against Pinnacle's close,
    and results.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy.stats import norm

import euro_dev_study as D
from backtest.analysis import df_to_md
from config_loader import ROOT, log_experiment
from euro_info_study import build as build_ratings
from features.euro_market import board_at, close_board, fair_curve, timelines, two_way

SIGMA = 17.0                     # rating-model residual SD (euro_info_study)
MIN_ODDS = 2.5
rng = np.random.default_rng(11)


def boot_ci(x: np.ndarray, stat, n: int = 2000):
    idx = rng.integers(0, len(x), (n, len(x)))
    sims = np.array([stat(x[i]) for i in idx])
    return np.percentile(sims, 2.5), np.percentile(sims, 97.5)


def q3(T, CC, final, model) -> tuple[pd.DataFrame, pd.DataFrame]:
    first_pin = T[T.book == "pinnacle"].groupby("fixture_id").t.min() + pd.Timedelta(milliseconds=1)
    B = board_at(T, first_pin)
    C0 = fair_curve(B)
    X = C0.merge(CC[["fixture_id", "fair_mu"]].rename(columns={"fair_mu": "close_mu"}), on="fixture_id")
    X["model"], X["total"] = X.fixture_id.map(model), X.fixture_id.map(final)
    X["start"] = X.fixture_id.map(T.groupby("fixture_id").start.first())
    X = X.dropna(subset=["model", "total"]).sort_values("start").reset_index(drop=True)
    X["dev_raw"] = X.model - X.fair_mu
    # point-in-time centring: subtract the mean disagreement of games on EARLIER dates
    day = X.start.dt.normalize()
    daily = X.groupby(day).dev_raw.agg(["sum", "size"])
    prior = (daily["sum"].cumsum() - daily["sum"]) / (daily["size"].cumsum() - daily["size"]).replace(0, np.nan)
    X["dev"] = X.dev_raw - day.map(prior).fillna(0.0).values
    X["move"] = X.close_mu - X.fair_mu
    X["resid"] = X.total - X.fair_mu
    r_move = np.corrcoef(X.dev, X.move)[0, 1]
    r_res = np.corrcoef(X.dev, X.resid)[0, 1]
    xy = X[["dev", "move", "resid"]].values
    ci_move = boot_ci(xy, lambda a: np.corrcoef(a[:, 0], a[:, 1])[0, 1])
    ci_res = boot_ci(xy, lambda a: np.corrcoef(a[:, 0], a[:, 2])[0, 1])
    y = (X.total > X.fair_mu).astype(float).values
    def ll(p):
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
    p_model = norm.cdf(X.dev / SIGMA)
    S = pd.DataFrame([{"games": len(X), "mean raw disagreement (pts)": X.dev_raw.mean(),
                       "SD of disagreement": X.dev.std(), "corr with Pinnacle's open->close move": r_move,
                       "  95% CI": ci_move, "corr with result vs Pinnacle's open": r_res, "  95% CI ": ci_res,
                       "log-loss gain x1e4 (model alone)": (ll(np.full(len(y), 0.5)) - ll(p_model)) * 1e4,
                       "log-loss gain x1e4 (half weight)": (ll(np.full(len(y), 0.5)) - ll(0.5 + 0.5 * (p_model - 0.5))) * 1e4}])
    # betting the model's side at Pinnacle's opening main line and price
    w = two_way(B[B.book == "pinnacle"])
    w = w[(w.line * 2) % 2 == 1]
    w["imb"] = (1 / w.over - 1 / w.under).abs()
    main = w.sort_values("imb").groupby("fixture_id").head(1).set_index("fixture_id")
    X = X[X.fixture_id.isin(main.index)].copy()
    m = main.loc[X.fixture_id]
    X["line"], X["side"] = m.line.values, np.where(X.dev > 0, "over", "under")
    X["price"] = np.where(X.side == "over", m.over.values, m.under.values)
    X["clv"] = D.fair_p(CC, X.fixture_id, X.line, X.side) * X.price - 1
    X["win"] = np.where(X.side == "over", X.total > X.line, X.total < X.line)
    X["pnl"] = np.where(X.win, X.price - 1, -1.0)
    rows = []
    for k in (0, 3, 5, 8):
        s = X[X.dev.abs() >= k]
        roi, ci = D.boot_roi(s)
        rows.append({"model disagrees by >= pts": k, "games": len(s),
                     "line moved toward model": (np.sign(s.move) == np.sign(s.dev)).mean(),
                     "mean CLV": s.clv.mean(), "won": s.win.mean(), "ROI": roi, "ROI 95% CI": ci})
    return S, pd.DataFrame(rows)


def q4(T, CC, final) -> pd.DataFrame:
    first_pin = T[T.book == "pinnacle"].groupby("fixture_id").t.min() + pd.Timedelta(milliseconds=1)
    start = T.groupby("fixture_id").start.first()
    times = {"when Pinnacle opens": first_pin, "6 h before tip": start - pd.Timedelta(hours=6)}
    rows = []
    for label, when in times.items():
        S = D.legs_at(T, when, CC, final)
        S = S[S.price.between(*D.BAND)]
        S["date"] = S.fixture_id.map(start).dt.tz_convert("Europe/Madrid").dt.date
        for thr in (0.0, 0.02):
            L = S[S.ev_now > thr].sort_values("ev_now").groupby("fixture_id").tail(1)    # best leg per game
            cards = []
            for d, g in L.groupby("date"):
                g = g.reset_index(drop=True)
                best = None
                for i in range(len(g)):
                    for j in range(i + 1, len(g)):
                        a, b = g.iloc[i], g.iloc[j]
                        if a.price * b.price < MIN_ODDS:
                            continue
                        ev = (1 + a.ev_now) * (1 + b.ev_now) - 1
                        if best is None or ev > best[0]:
                            best = (ev, a, b)
                if best and best[0] > 0:
                    ev, a, b = best
                    odds = a.price * b.price
                    win = bool(a.win and b.win)
                    cards.append({"date": d, "fixture_id": f"{a.fixture_id}|{b.fixture_id}", "odds": odds,
                                  "ev": ev, "clv": (1 + a.clv) * (1 + b.clv) - 1, "win": win,
                                  "pnl": odds - 1 if win else -1.0})
            C = pd.DataFrame(cards)
            if C.empty:
                rows.append({"decision time": label, "leg EV >": thr, "cards": 0})
                continue
            roi, ci = D.boot_roi(C)
            rows.append({"decision time": label, "leg EV >": thr, "cards": len(C), "mean odds": C.odds.mean(),
                         "break-even": (1 / C.odds).mean(), "mean joint EV": C.ev.mean(),
                         "mean joint CLV": C.clv.mean(), "CLV > 0": (C.clv > 0).mean(),
                         "both won": C.win.mean(), "ROI": roi, "ROI 95% CI": ci})
    return pd.DataFrame(rows)


def main():
    T = timelines()
    T = T[(T.start >= D.DEV_FROM) & (T.start < D.DEV_TO)].drop_duplicates(["fixture_id", "book", "line", "side", "t"])
    final, F = D.results(T)
    G = build_ratings()
    model = F.set_index("fixture_id").game_key.map(G.set_index("game_key").exp_total)
    CC = fair_curve(close_board(T))
    S3, B3 = q3(T, CC, final, model)
    Q4 = q4(T, CC, final)
    lines = ["# Europe development study: the model and the 2.5 cards (Q3, Q4)\n",
             f"Development games with Pinnacle's opening and closing ladders and a model total: "
             f"**{int(S3.games.iloc[0])}** (2025-26, from 2026-01-20). Small sample: read for direction.\n",
             "## Q3 — does the rating model add information to Pinnacle's opener?\n",
             "Disagreement = model total - Pinnacle's no-vig opening line, centred on the average "
             "disagreement of earlier dates (no look-ahead).\n", df_to_md(S3, "{:.3f}"), "",
             "Betting the model's side at Pinnacle's opening main line and price:\n", df_to_md(B3, "{:.3f}"), "",
             "## Q4 — two-leg cards at combined odds >= 2.5 from real soft-book prices\n",
             "Legs 1.40-1.90 from 1xBet/Betway/Unibet/bet365 whose price beats Pinnacle's fair price at the "
             "decision time; per date, the pair of games with the highest joint EV (released only if > 0). "
             "Joint CLV values the card at Pinnacle's closing fair prices.\n", df_to_md(Q4, "{:.3f}"), ""]
    out = ROOT / "reports" / "euro_dev_q3q4.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("euro_dev_q3q4", {"sigma": SIGMA, "min_odds": MIN_ODDS, "band": D.BAND},
                   {"q3": S3.to_dict("records"), "q3_bets": B3.to_dict("records"), "q4": Q4.to_dict("records")})


if __name__ == "__main__":
    main()
