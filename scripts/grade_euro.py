"""Grade the European forward ledger (reports/live_ledger_euro.csv): results from the official
EuroLeague / EuroCup feed, and each pick's closing-line value against Pinnacle's last price before
tip-off in the saved odds snapshots (the low-noise check that the edge is real).

usage: python scripts/grade_euro.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from data import oddsapi
from data.euroleague import parse, season_games
from features.euro_market import fair_curve, fair_p
from models.live_euro import CUR_CODES

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "reports" / "live_ledger_euro.csv"


def finals() -> pd.Series:
    for code in CUR_CODES:
        try:
            season_games(code, max_age_hours=0.5)
        except Exception as e:                                   # noqa: BLE001
            print(f"  could not refresh {code}: {e}")
    G, _ = parse(CUR_CODES)
    return G.set_index("game_key").total


def closing_fair(fixture_id: str, start: pd.Timestamp, line: float, side: str) -> float:
    """Pinnacle's no-vig probability for the pick at the last snapshot taken before tip-off."""
    for p in sorted(oddsapi.SNAP.glob("basketball_euroleague_*.json"), reverse=True):
        t = pd.to_datetime(p.stem.split("_")[-1], format="%Y%m%dT%H%M%SZ", utc=True)
        if t >= start:
            continue
        B = oddsapi.board(p)
        B = B[B.fixture_id == fixture_id]
        if B.empty:
            continue
        c = fair_curve(B, whole_lines=True)
        if not c.empty:
            return float(fair_p(c, [fixture_id], [line], [side])[0])
    return np.nan


def main():
    if not LEDGER.exists():
        sys.exit("no European picks recorded yet (scripts/predict_euro.py --update --record)")
    D = pd.read_csv(LEDGER, parse_dates=["start"])
    tot = finals()
    D["total"] = D.game_key.map(tot)
    played = D.total.notna()
    win = np.where(D.side == "over", D.total > D.line, D.total < D.line)
    D["result"] = np.where(~played, "pending", np.where(D.total == D.line, "push", np.where(win, "won", "lost")))
    D["close_p"] = [closing_fair(f, s, l, sd) for f, s, l, sd in zip(D.fixture_id, D.start, D.line, D.side)]
    D["clv"] = D.close_p * D.price - 1

    S = D[D.kind == "single"]
    g = S[S.result != "pending"]
    pnl = np.where(g.result == "won", g.price - 1, np.where(g.result == "lost", -1.0, 0.0))
    print(f"Singles: {len(S)} recorded, {len(g)} graded: {int((g.result == 'won').sum())} won, "
          f"{int((g.result == 'lost').sum())} lost" + (f", ROI {pnl.mean():+.1%}" if len(g) else "") +
          (f"; average value at bet time {S.ev.mean():+.1%}, against the close {S.clv.mean():+.1%} "
           f"({int(S.clv.notna().sum())} with a closing price)" if len(S) else ""))
    C = D[D.kind == "card"]
    if len(C):
        rows = []
        for cid, c in C.groupby("card"):
            odds = float(np.prod(c.price))
            if (c.result == "pending").any():
                res, pnl = "pending", np.nan
            elif (c.result == "lost").any():
                res, pnl = "lost", -1.0
            else:                                                 # a pushed leg pays 1.0 (none on half-point lines)
                pnl = float(np.prod(np.where(c.result == "push", 1.0, c.price)) - 1)
                res = "won" if pnl > 0 else "push"
            rows.append({"card": cid, "odds": odds, "result": res, "pnl": pnl})
        R = pd.DataFrame(rows)
        done = R[R.result != "pending"]
        print(f"2.5+ cards: {len(R)} recorded, {len(done)} graded: {int((done.result == 'won').sum())} won"
              + (f", ROI {done.pnl.mean():+.1%}" if len(done) else ""))
    out = ROOT / "reports" / "live_ledger_euro_graded.csv"
    D.to_csv(out, index=False)
    print(f"details: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
