"""Stage 3 — odds-targeted two-pick cards (combined offered odds >= a floor, e.g. 2.5).

For every eligible game and side the engine builds a ladder of candidate legs:
  * MAIN leg      : the best book's opening number for that side at that book's REAL price
                    (archive seasons without prices: the archived opener at 1.909)
  * ALTERNATE legs: integer buffers k in [-6, +15] from the market (median) opener, priced
                    (1 - margin) / p_market(line) — the market's own no-model probability
Each leg gets a model probability and a CONSERVATIVE probability from the edge-aware
calibrator. A card = two legs from different games maximising the conservative EV
    p_cons_A * p_cons_B * odds_A * odds_B - 1      subject to odds_A * odds_B >= floor,
released only when that conservative EV is > 0. Pushes are voids (as books settle).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtest.wf2 import Z95

K_ALT = np.arange(-6, 16, 1.0)


def american_to_decimal(a):
    a = np.asarray(pd.to_numeric(pd.Series(np.atleast_1d(a)), errors="coerce"), float)
    out = np.where(a >= 100, 1 + a / 100.0, np.where(a <= -100, 1 + 100.0 / np.abs(a), np.nan))
    return out


MAX_BOOK_DEV = 3.0   # a book's opener > 3 pts from the cross-book median is treated as a data error


def best_main(books_json, side: int, max_dev: float = MAX_BOOK_DEV):
    """(line, decimal price, book) of the best opening number for `side` across books.
    Outlier guard: books whose opener sits more than `max_dev` points from the median
    opener of all books are ignored (stale/erroneous numbers that were never bettable)."""
    if not isinstance(books_json, str):
        return np.nan, np.nan, None
    try:
        books = json.loads(books_json)
    except Exception:  # noqa: BLE001
        return np.nan, np.nan, None
    opens = [b.get("open") for b in books.values() if b.get("open") is not None]
    med = float(np.median(opens)) if opens else np.nan
    best = None
    for name, b in books.items():
        line = b.get("open")
        if line is not None and max_dev is not None and abs(line - med) > max_dev:
            continue
        price = b.get("open_over") if side == 1 else b.get("open_under")
        if line is None or price is None:
            continue
        dec = float(american_to_decimal(price)[0])
        if np.isnan(dec):
            continue
        key = (-line if side == 1 else line, dec)
        if best is None or key > best[0]:
            best = (key, float(line), dec, name)
    return (best[1], best[2], best[3]) if best else (np.nan, np.nan, None)


@dataclass
class LegSet:
    frame: pd.DataFrame          # one row per game (calibrated, eligible)
    thr: np.ndarray              # (n, 2, K+1) thresholds; index 0 = main leg
    p: np.ndarray                # model win probability
    p_cons: np.ndarray           # conservative win probability
    p_mkt: np.ndarray            # market-only probability (for modelled prices)
    p_mkt_close: np.ndarray      # same, centred on the closing line (stress test)
    real_odds: np.ndarray        # (n, 2) real price of the main leg (nan if none)
    win: np.ndarray
    push: np.ndarray


def build_legs(P: pd.DataFrame, cals: dict, calm: dict, books: pd.Series | None = None,
               alt_ref: str = "median") -> LegSet:
    """alt_ref 'median'   : alternate ladder around the consensus (median) opener
       alt_ref 'best_book': ladder from the book whose opener is best for that side, priced
                            around THAT book's line (line shopping for alternates)."""
    P = P[P.calibrated & P.eligible].reset_index(drop=True)
    n = len(P)
    nk = len(K_ALT) + 1
    thr = np.full((n, 2, nk), np.nan)
    real = np.full((n, 2), np.nan)
    ref = np.full((n, 2), np.nan)                 # line each ladder is priced around
    line = P.line.values
    for s_i, side in enumerate((1, -1)):
        # main leg: best book's opener + real price; fallback: the market line at 1.909
        if books is not None:
            bj = books.reindex(P.game_key).values
            bm = [best_main(b, side) for b in bj]
            bl = np.array([x[0] for x in bm], float)
            bp = np.array([x[1] for x in bm], float)
        else:
            bl = np.full(n, np.nan)
            bp = np.full(n, np.nan)
        main_line = np.where(np.isnan(bl), line, bl)
        ref[:, s_i] = main_line if alt_ref == "best_book" else line
        r = ref[:, s_i]
        base = (np.ceil(r + 0.5) - 0.5) if side == 1 else (np.floor(r - 0.5) + 0.5)
        thr[:, s_i, 1:] = base[:, None] - side * K_ALT[None, :]
        thr[:, s_i, 0] = main_line
        real[:, s_i] = np.where(np.isnan(bp), 1.909, bp)
    out = P.outcome.values
    win = np.zeros((n, 2, nk), bool)
    push = np.zeros((n, 2, nk), bool)
    win[:, 0, :] = out[:, None] > thr[:, 0, :]
    win[:, 1, :] = out[:, None] < thr[:, 1, :]
    push[:] = out[:, None, None] == thr
    p = np.full((n, 2, nk), np.nan)
    pc = np.full((n, 2, nk), np.nan)
    pm = np.full((n, 2, nk), np.nan)
    pmc = np.full((n, 2, nk), np.nan)
    close = P.line_close.values if "line_close" in P else np.full(n, np.nan)
    for season, idx in P.groupby("season").groups.items():
        idx = np.asarray(idx)
        cal, cm = cals[season], calm[season]
        for s_i, side in enumerate((1, -1)):
            for k in range(nk):
                t = thr[idx, s_i, k]
                # continuity: an integer line wins only on the next whole point
                t_eff = np.where(t == np.floor(t), t + 0.5 * side, t)
                sm = side * P.mu.values[idx] / P.sd.values[idx]
                sb = side * (line[idx] - t_eff) / P.sd.values[idx]
                pp, lo = cal.prob(sm, sb, z=Z95, side=side)
                p[idx, s_i, k], pc[idx, s_i, k] = pp, lo
                smm = side * P.mu_mkt.values[idx] / P.sd_mkt.values[idx]
                sbm = side * (ref[idx, s_i] - t_eff) / P.sd_mkt.values[idx]   # book prices around its line
                pm[idx, s_i, k] = cm.prob(smm, sbm)
                sbc = side * (close[idx] - t_eff) / P.sd_mkt.values[idx]
                pmc[idx, s_i, k] = np.where(np.isnan(close[idx]), np.nan, cm.prob(smm, np.nan_to_num(sbc)))
    return LegSet(P, thr, p, pc, pm, pmc, real, win, push)


def leg_odds(L: LegSet, margin: float, main_only: bool, price_ref: str = "open") -> np.ndarray:
    """Offered odds for every leg: real price for the main leg, modelled for alternates
    (priced off the opening line, or — stress test — off the closing line)."""
    pm = L.p_mkt if price_ref == "open" else L.p_mkt_close
    o = (1 - margin) / np.clip(pm, 1e-3, 1)
    o[:, :, 0] = L.real_odds
    if main_only:
        o[:, :, 1:] = np.nan
    return o


def settle(win_a, push_a, oa, win_b, push_b, ob):
    if (not win_a and not push_a) or (not win_b and not push_b):
        return -1.0
    return (oa if win_a else 1.0) * (ob if win_b else 1.0) - 1.0


def odds_cards(L: LegSet, floor: float = 2.5, margin: float = 0.045, main_only: bool = False,
               leg_band: tuple | None = None, combo_cap: float | None = None,
               top_n: int = 16, force: bool = False, ev_gate: str = "conservative",
               objective: str = "ev", price_ref: str = "open",
               settle_price_ref: str | None = None) -> pd.DataFrame:
    """objective 'ev'   : maximise conservative EV subject to the odds floor
       objective 'joint': maximise the conservative probability that BOTH legs win,
                          subject to the odds floor and conservative EV > 0
       price_ref        : prices used for SELECTION; settle_price_ref: prices used to
                          SETTLE (default = same). 'close' = alternates priced off the close."""
    F = L.frame
    odds = leg_odds(L, margin, main_only, price_ref)
    odds_settle = odds if settle_price_ref in (None, price_ref) else leg_odds(L, margin, main_only, settle_price_ref)
    if leg_band is not None:
        odds = np.where((odds >= leg_band[0]) & (odds <= leg_band[1]), odds, np.nan)
    v_cons = L.p_cons * odds
    v_mod = L.p * odds
    rows = []
    for date, idx in F.groupby("date").groups.items():
        idx = np.asarray(idx)
        if len(idx) < 2:
            continue
        cand = []
        for gi in idx:
            for s_i in range(2):
                vc = v_cons[gi, s_i]
                if np.all(np.isnan(vc)):
                    continue
                cand.append((np.nanmax(vc), gi, s_i))
        cand.sort(reverse=True)
        cand = cand[:top_n]
        best = None
        for a in range(len(cand)):
            for b in range(a + 1, len(cand)):
                _, ga, sa = cand[a]
                _, gb, sb = cand[b]
                if ga == gb:
                    continue
                oa, ob = odds[ga, sa], odds[gb, sb]
                combo = oa[:, None] * ob[None, :]
                ok = combo >= floor
                if combo_cap is not None:
                    ok &= combo <= combo_cap
                if not np.any(ok):
                    continue
                evc = v_cons[ga, sa][:, None] * v_cons[gb, sb][None, :]
                if objective == "joint":
                    ok &= evc > 1.0
                    score = np.where(ok, L.p_cons[ga, sa][:, None] * L.p_cons[gb, sb][None, :], -np.inf)
                else:
                    score = np.where(ok, evc, -np.inf)
                score = np.nan_to_num(score, nan=-np.inf)
                ka, kb = np.unravel_index(np.argmax(score), score.shape)
                if not np.isfinite(score[ka, kb]):
                    continue
                if best is None or score[ka, kb] > best[0]:
                    best = (score[ka, kb], ga, sa, ka, gb, sb, kb)
        if best is None:
            continue
        sc, ga, sa, ka, gb, sb, kb = best
        ev_cons = v_cons[ga, sa, ka] * v_cons[gb, sb, kb] - 1
        ev_model = v_mod[ga, sa, ka] * v_mod[gb, sb, kb] - 1
        gate = ev_cons if ev_gate == "conservative" else ev_model
        if not force and gate <= 0:
            continue
        oa, ob = odds_settle[ga, sa, ka], odds_settle[gb, sb, kb]
        wa, wb = bool(L.win[ga, sa, ka]), bool(L.win[gb, sb, kb])
        pa_, pb_ = bool(L.push[ga, sa, ka]), bool(L.push[gb, sb, kb])
        rows.append({
            "date": date, "season": F.season.values[ga],
            "game_a": F.game_key.values[ga], "side_a": 1 - 2 * sa, "thr_a": L.thr[ga, sa, ka],
            "main_a": ka == 0, "odds_a": oa, "p_a": L.p[ga, sa, ka], "pc_a": L.p_cons[ga, sa, ka],
            "game_b": F.game_key.values[gb], "side_b": 1 - 2 * sb, "thr_b": L.thr[gb, sb, kb],
            "main_b": kb == 0, "odds_b": ob, "p_b": L.p[gb, sb, kb], "pc_b": L.p_cons[gb, sb, kb],
            "combined_odds": oa * ob, "joint_model": L.p[ga, sa, ka] * L.p[gb, sb, kb],
            "joint_cons": L.p_cons[ga, sa, ka] * L.p_cons[gb, sb, kb],
            "ev_model": ev_model, "ev_cons": ev_cons,
            "win_a": wa, "win_b": wb, "push_a": pa_, "push_b": pb_,
            "profit": settle(wa, pa_, oa, wb, pb_, ob),
        })
        rows[-1]["card_win"] = int(rows[-1]["profit"] > 0)
    return pd.DataFrame(rows)


def summarize(C: pd.DataFrame, n_slates: int | None = None, n_boot: int = 2000, seed: int = 0) -> dict:
    from calibration.calibrate import wilson
    if C.empty:
        return {"cards": 0}
    n = len(C)
    k = int(C.card_win.sum())
    lo, hi = wilson(k, n)
    rng = np.random.default_rng(seed)
    by_date = C.groupby("date").profit.sum()
    cnt = C.groupby("date").size()
    vals, cnts = by_date.values, cnt.values
    boots = []
    for _ in range(n_boot):
        i = rng.integers(0, len(vals), len(vals))
        boots.append(vals[i].sum() / cnts[i].sum())
    eq = C.sort_values("date").profit.cumsum().values
    dd = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    lose = (C.sort_values("date").profit.values < 0)
    best = cur = 0
    for x in lose:
        cur = cur + 1 if x else 0
        best = max(best, cur)
    out = {"cards": n, "won": k, "hit_rate": k / n, "hit_ci95": (lo, hi),
           "avg_combined_odds": float(C.combined_odds.mean()),
           "breakeven_hit": float((1 / C.combined_odds).mean()),
           "model_hit": float(C.joint_model.mean()), "cons_hit": float(C.joint_cons.mean()),
           "roi": float(C.profit.mean()), "roi_ci95": tuple(np.percentile(boots, [2.5, 97.5])),
           "units": float(C.profit.sum()), "max_drawdown": dd, "longest_losing_run": best,
           "share_main_legs": float((C.main_a.sum() + C.main_b.sum()) / (2 * n)),
           "leg_win": float((C.win_a.sum() + C.win_b.sum()) / (2 * n)),
           "leg_model_p": float((C.p_a + C.p_b).mean() / 2)}
    if n_slates:
        out["pct_slates"] = n / n_slates
    return out
