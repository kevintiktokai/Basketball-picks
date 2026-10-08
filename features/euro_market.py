"""Bookmaker totals timelines for European games (OddsPapi cache) and Pinnacle fair prices.

Everything here reads only the cached pre-game snapshots written by data/oddspapi.py.

* timelines(): one row per price update (fixture, book, line, side, time, price, active).
* board_at(): the prices in force at a decision time (the feed records changes only, so a
  price stays in force until its next update; an inactive update means not offered).
* fair_curve(): Pinnacle's no-vig P(over) at any line, from its ladder at that moment:
  probit(P) is fitted as a straight line in the total (a normal model), so lines outside
  Pinnacle's ladder are extrapolated smoothly.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import norm

from data import oddspapi as op

SIGMA_DEFAULT = 16.0          # points; used only when Pinnacle shows a single line


def timelines(paths=None) -> pd.DataFrame:
    M = op.markets()
    tot = M[(M.kind == "totals") & M.full_game & M.side.isin(["over", "under"])]
    tot = tot.drop_duplicates("outcome_id").set_index("outcome_id")
    rows = []
    for p in paths or sorted(op.RAW.glob("*/hist/*.json")):
        d = json.loads(p.read_text())
        f = d.get("_fixture") or {}
        if not d.get("bookmakers"):
            continue
        start = op._start(f)
        for book, bd in d["bookmakers"].items():
            for md in bd["markets"].values():
                for oid, od in md["outcomes"].items():
                    oid = int(oid)
                    if oid not in tot.index:
                        continue
                    line, side = float(tot.at[oid, "line"]), tot.at[oid, "side"]
                    for s in (od.get("players") or {}).get("0") or []:
                        rows.append((f["fixtureId"], d.get("_tid"), start, f.get("participant1Name"),
                                     f.get("participant2Name"), book, line, side, s["createdAt"],
                                     s.get("price"), s.get("active", True) is not False, s.get("limit")))
    T = pd.DataFrame(rows, columns=["fixture_id", "tid", "start", "home_name", "away_name", "book", "line",
                                    "side", "t", "price", "active", "limit"])
    T["t"] = pd.to_datetime(T.t, utc=True)
    return T.sort_values(["fixture_id", "book", "line", "side", "t"]).reset_index(drop=True)


def board_at(T: pd.DataFrame, when: pd.Series) -> pd.DataFrame:
    """Prices in force at `when` (a Series indexed by fixture_id): the last update at or before
    that time per book/line/side, kept only if that update was active."""
    W = T.merge(when.rename("when"), left_on="fixture_id", right_index=True)
    W = W[W.t <= W.when]
    B = W.groupby(["fixture_id", "book", "line", "side"], as_index=False).tail(1)
    return B[B.active & (B.price > 1.0)].drop(columns=["active"]).reset_index(drop=True)


def two_way(B: pd.DataFrame) -> pd.DataFrame:
    w = B.pivot_table(index=["fixture_id", "book", "line"], columns="side", values="price", aggfunc="last")
    return w.dropna(subset=["over", "under"]).reset_index() if {"over", "under"} <= set(w.columns) else \
        pd.DataFrame(columns=["fixture_id", "book", "line", "over", "under"])


def fair_curve(B: pd.DataFrame, book: str = "pinnacle") -> pd.DataFrame:
    """Per fixture: (a, b) with no-vig P(over at line x) = Phi(a - b*x), fitted on the book's
    half-point lines with both sides offered, plus its main (most balanced) line."""
    w = two_way(B[B.book == book])
    w = w[(w.line * 2) % 2 == 1]                                  # half-point lines: no pushes
    w["p"] = (1 / w.over) / (1 / w.over + 1 / w.under)
    out = []
    for fid, g in w.groupby("fixture_id"):
        z = norm.ppf(g.p.clip(0.02, 0.98))
        if len(g) >= 2 and g.line.nunique() >= 2:
            slope, icpt = np.polyfit(g.line, z, 1)
            b = -slope if -slope > 1 / 40 else 1 / SIGMA_DEFAULT        # guard against flat/odd fits
            a = float(np.mean(z + b * g.line))
        else:
            b = 1 / SIGMA_DEFAULT
            a = float(z[0] + b * g.line.iloc[0])
        main = g.iloc[(g.p - 0.5).abs().argmin()]
        out.append({"fixture_id": fid, "a": a, "b": b, "fair_mu": a / b, "pin_main": main.line,
                    "pin_lines": len(g)})
    return pd.DataFrame(out)


def fair_p(curve: pd.DataFrame, fixture_id, line, side) -> np.ndarray:
    """Vectorised no-vig probability of `side` winning at `line` (half-point lines)."""
    c = curve.set_index("fixture_id").reindex(fixture_id)
    p_over = norm.cdf(c.a.values - c.b.values * np.asarray(line, float))
    return np.where(np.asarray(side) == "over", p_over, 1 - p_over)


def close_board(T: pd.DataFrame, tolerance_min: float = 30) -> pd.DataFrame:
    """Closing prices: each line's last active pre-game price, kept if the line was still offered
    within `tolerance_min` of the book's last pre-game update (books suspend just before tip)."""
    last = T.groupby(["fixture_id", "book", "line", "side"], as_index=False).tail(1)
    end = last.groupby(["fixture_id", "book"]).t.transform("max")
    offered = last.active | ((end - last.t) <= pd.Timedelta(minutes=tolerance_min))
    keep = last.loc[offered, ["fixture_id", "book", "line", "side"]]
    act = T[T.active & (T.price > 1.0)].groupby(["fixture_id", "book", "line", "side"], as_index=False).tail(1)
    return act.merge(keep, on=["fixture_id", "book", "line", "side"])
