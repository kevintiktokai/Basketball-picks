"""Two-pick card selection engine and card-level backtest (Sections 1, 24, 25).

Per slate:
  1. screen individual Over candidates (data quality, calibrated, P >= floor,
     positive EV, positive model edge)
  2. enumerate all pairs
  3. estimate P(A), P(B), P(A and B) via the dependence model
  4. conservative joint = copula(conservative marginals, lower-bound rho)
  5. discard pairs with conservative joint < target
  6. rank survivors by calibrated joint probability (joint EV as tie-break)
  7. release TWO-PICK CARD / ONE QUALIFYING PICK / NO BET

The SAME function is used by the backtest and by the live CLI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd

from backtest.dependence import joint_probability
from calibration.calibrate import wilson


@dataclass
class SelectionParams:
    joint_target: float = 0.60
    individual_floor: float = 0.60      # necessary: P(A and B) <= min(P(A), P(B))
    single_cons_min: float = 0.5238     # single-pick standard: conservative P beats -110 break-even
    min_edge_points: float = 0.0
    rho_hat: float = 0.0
    rho_lo: float = 0.0
    odds: float = 1.909


@dataclass
class SlateDecision:
    date: object
    outcome: str                         # TWO-PICK CARD / ONE QUALIFYING PICK / NO BET
    n_games: int
    n_candidates: int
    n_pairs: int
    n_qualifying_pairs: int
    picks: list = field(default_factory=list)
    joint_cal: float = np.nan
    joint_cons: float = np.nan
    joint_indep: float = np.nan
    best_rejected: dict | None = None


def ev_single(p, odds):
    return p * odds - 1.0


def decide_slate(day: pd.DataFrame, sp: SelectionParams) -> SlateDecision:
    day = day[day.calibrated & day.eligible_data]
    if "odds" not in day:
        day = day.assign(odds=sp.odds)
    cand = day[(day.p_cal >= sp.individual_floor)
               & (ev_single(day.p_cal, day.odds) > 0)
               & (day.proj_total - day.line > sp.min_edge_points)]
    dec = SlateDecision(date=day.date.iloc[0] if len(day) else None, outcome="NO BET",
                        n_games=len(day), n_candidates=len(cand), n_pairs=0, n_qualifying_pairs=0)

    # closest pair overall (for "best rejected" reporting), from all calibrated games
    pool = day.nlargest(min(len(day), 8), "p_cal")
    best_any = None
    for (_, a), (_, b) in combinations(pool.iterrows(), 2):
        jc = joint_probability(a.p_cons, b.p_cons, sp.rho_lo)
        if best_any is None or jc > best_any["joint_cons"]:
            best_any = {"a": a.game_id, "b": b.game_id, "joint_cons": float(jc),
                        "joint_cal": float(joint_probability(a.p_cal, b.p_cal, sp.rho_hat))}
    dec.best_rejected = best_any

    pairs = []
    for (_, a), (_, b) in combinations(cand.iterrows(), 2):
        jcal = float(joint_probability(a.p_cal, b.p_cal, sp.rho_hat))
        jcons = float(joint_probability(a.p_cons, b.p_cons, sp.rho_lo))
        ev_dbl = jcal * a.odds * b.odds - 1.0
        pairs.append((a, b, jcal, jcons, ev_dbl))
    dec.n_pairs = len(pairs)
    qual = [p for p in pairs if p[3] >= sp.joint_target]
    dec.n_qualifying_pairs = len(qual)
    if qual:
        a, b, jcal, jcons, _ = max(qual, key=lambda t: (t[2], t[4]))
        dec.outcome = "TWO-PICK CARD"
        dec.picks = [a, b]
        dec.joint_cal, dec.joint_cons = jcal, jcons
        dec.joint_indep = float(a.p_cal * b.p_cal)
        return dec
    singles = cand[(cand.p_cons >= sp.single_cons_min) & (ev_single(cand.p_cons, cand.odds) > 0)]
    if len(singles):
        dec.outcome = "ONE QUALIFYING PICK"
        dec.picks = [singles.loc[singles.p_cal.idxmax()]]
    return dec


# ------------------------------------------------------------------ backtest
def leg_result(row) -> str:
    if row.total > row.line:
        return "W"
    if row.total == row.line:
        return "P"
    return "L"


def run_card_backtest(pred: pd.DataFrame, sp: SelectionParams) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (slates, released_picks). Card result: 2/2 only if both legs WIN
    (a pushed leg is NOT a win for the 2/2 metric)."""
    slates, picks = [], []
    for date, day in pred.groupby("date", sort=True):
        dec = decide_slate(day, sp)
        rec = {"date": date, "season": day.season.iloc[0], "outcome": dec.outcome,
               "n_games": dec.n_games, "n_candidates": dec.n_candidates,
               "n_pairs": dec.n_pairs, "n_qualifying_pairs": dec.n_qualifying_pairs,
               "joint_cal": dec.joint_cal, "joint_cons": dec.joint_cons,
               "joint_indep": dec.joint_indep,
               "closest_pair_joint_cons": dec.best_rejected["joint_cons"] if dec.best_rejected else np.nan}
        res = [leg_result(p) for p in dec.picks]
        if dec.outcome == "TWO-PICK CARD":
            wins = sum(r == "W" for r in res)
            rec["card_wins"] = wins
            rec["card_2of2"] = int(wins == 2)
            rec["singles_profit"] = sum(_single_profit(r, sp.odds) for r in res)
            rec["double_profit"] = _double_profit(res, sp.odds)
        slates.append(rec)
        for k, (p, r) in enumerate(zip(dec.picks, res)):
            picks.append({"date": date, "season": p.season, "game_id": p.game_id, "role": dec.outcome,
                          "leg": k, "line": p.line, "proj_total": p.proj_total, "p_raw": p.p_raw,
                          "p_cal": p.p_cal, "p_cons": p.p_cons, "total": p.total, "result": r,
                          "profit": _single_profit(r, sp.odds)})
    return pd.DataFrame(slates), pd.DataFrame(picks)


def _single_profit(r, odds):
    return {"W": odds - 1.0, "P": 0.0, "L": -1.0}[r]


def _double_profit(res, odds):
    if "L" in res:
        return -1.0
    mult = 1.0
    for r in res:
        mult *= odds if r == "W" else 1.0
    return mult - 1.0


def card_metrics(slates: pd.DataFrame) -> dict:
    cards = slates[slates.outcome == "TWO-PICK CARD"]
    n = len(cards)
    out = {
        "slates": int(len(slates)),
        "pct_two_pick": float((slates.outcome == "TWO-PICK CARD").mean()) if len(slates) else np.nan,
        "pct_one_pick": float((slates.outcome == "ONE QUALIFYING PICK").mean()) if len(slates) else np.nan,
        "pct_no_bet": float((slates.outcome == "NO BET").mean()) if len(slates) else np.nan,
        "two_pick_cards": n,
    }
    if n == 0:
        return out
    k = int(cards.card_2of2.sum())
    lo, hi = wilson(k, n)
    eq = cards.double_profit.cumsum()
    out.update({
        "cards_2of2": k, "cards_1of2": int((cards.card_wins == 1).sum()),
        "cards_0of2": int((cards.card_wins == 0).sum()),
        "rate_2of2": k / n, "ci95": (lo, hi),
        "avg_joint_cal": float(cards.joint_cal.mean()), "avg_joint_cons": float(cards.joint_cons.mean()),
        "roi_singles_per_card": float(cards.singles_profit.sum() / (2 * n)),
        "roi_double": float(cards.double_profit.mean()),
        "max_drawdown_double_units": float((eq.cummax() - eq).max()),
    })
    return out
