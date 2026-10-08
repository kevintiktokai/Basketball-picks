"""Loss autopsy, round 3: a pre-game version of round 2's near-miss "key player out".

Round 2 read who played from the game's own box score (t -1.91 / -2.08: totals came in under the
engine's forecast when a 25+ minute player sat, but discovery missed the |t| >= 2 bar). An absence
is usually known before the opener only because the player already missed the previous game, so
this round uses only earlier box scores. Ideas and expected directions, written before the first run:
  missed last game     a key player (25+ minutes a game over the five games before his team's last
                       game) did not play in that last game; both teams; expected -
  missed last two      the same, but he missed both of the last two games; expected -
Same data and rule as rounds 1-2 (2011-21 only; |t| >= 2 in discovery and the same sign with
|t| >= 1.5 in validation). Also reported: how often such a player then sits again.
Writes reports/loss_autopsy_round3.md.
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

import loss_autopsy as LA
from backtest.analysis import df_to_md
from backtest.wf2 import main_line_probs
from config_loader import ROOT, log_experiment
from diagnose_bets import load

KEY_MIN, PREV_GAMES = 25.0, 5


def previous_absences(G: pd.DataFrame):
    from data.ncaab_players import load as load_players
    pb = load_players(range(2011, 2022))
    pb = pb[pb.athlete_id.notna()].copy()
    pb["team_id"] = pd.to_numeric(pb.team_id, errors="coerce").astype("Int64")
    pb["m"] = np.where(pb.did_not_play.fillna(False).astype(bool), 0.0, pb.minutes.fillna(0.0))
    pb = pb.drop_duplicates(["game_id", "team_id", "athlete_id"])
    rows, again1, again2 = [], [], []
    for (team, _), g in pb.groupby(["team_id", "season"]):
        order = g.groupby("game_id").agg(date=("game_date", "first"), tot=("m", "sum"))
        order = order[order.tot > 0].sort_values("date")
        gids = order.index.values
        W = g.pivot(index="game_id", columns="athlete_id", values="m").reindex(gids).fillna(0.0).values
        for j in range(len(gids)):
            m1, m2 = np.nan, np.nan
            if j >= 4:                                  # at least three games before the last one
                prev = W[max(0, j - 1 - PREV_GAMES):j - 1].mean(axis=0)
                key = prev >= KEY_MIN
                miss1 = key & (W[j - 1] == 0)
                m1 = float(prev[miss1].sum() / 200)
                again1 += list(W[j][miss1] == 0)
                if j >= 5:
                    prev2 = W[max(0, j - 2 - PREV_GAMES):j - 2].mean(axis=0)
                    miss2 = (prev2 >= KEY_MIN) & (W[j - 1] == 0) & (W[j - 2] == 0)
                    m2 = float(prev2[miss2].sum() / 200)
                    again2 += list(W[j][miss2] == 0)
            rows.append((gids[j], int(team), m1, m2))
    A = pd.DataFrame(rows, columns=["game_id", "team_id", "m1", "m2"]).set_index(["game_id", "team_id"])
    X = pd.DataFrame(index=G.index)
    parts = {}
    for side in ("home", "away"):
        idx = pd.MultiIndex.from_arrays([G.espn_game_id.fillna(-1).astype("int64"),
                                         pd.to_numeric(G[side].str[1:], errors="coerce").fillna(-1).astype("int64")])
        parts[side] = A.reindex(idx)
    for c, lab in (("m1", "missed_last"), ("m2", "missed_last2")):
        share = parts["home"][c].values + parts["away"][c].values
        X[f"{lab}_share"] = share
        X[lab] = np.where(np.isfinite(share), (share > 0).astype(float), np.nan)
    persist = {"missed the last game": (len(again1), float(np.mean(again1))),
               "missed the last two": (len(again2), float(np.mean(again2)))}
    return X, persist


def main():
    P, cals, _ = load()
    P = P[P.season.isin(LA.ERA)]
    M = main_line_probs(P, cals)
    M = M[M.eligible].copy()
    M["era"] = M.season.map(LA.ERA)
    G = M.reset_index(drop=True)
    G["r"] = G.outcome - G.line - G.mu
    G["bet"] = (G.p_best >= LA.P_MIN) & ~G.best_push
    G["won"] = G.best_win.astype(int)
    G["margin"] = G.best_side * (G.outcome - G.line)
    X, persist = previous_absences(G)
    G = pd.concat([G, X], axis=1)
    eras = list(dict.fromkeys(LA.ERA.values()))
    ideas = {"key player missed the last game": "missed_last", "key minutes that missed the last game (share)": "missed_last_share",
             "key player missed the last two games": "missed_last2", "key minutes that missed the last two (share)": "missed_last2_share"}
    rows, bet_rows = [], []
    for label, col in ideas.items():
        rec = {"idea": label, "expected": "-"}
        for era in eras:
            E = G[G.era == era]
            short = "disc" if era.startswith("disc") else "val"
            rec[f"t all games ({short})"], rec[f"games ({short})"] = LA.t_stat(E[col].values.astype(float), E.r.values.astype(float))
            Bt = E[E.bet]
            rec[f"t our bets ({short})"], _ = LA.t_stat(Bt[col].values.astype(float), Bt.margin.values.astype(float))
            if not col.endswith("share"):
                rec[f"flagged ({short})"] = int(np.nansum(E[col]))
                rec[f"miss when flagged ({short})"] = float(E.r[E[col] == 1].mean())
                for side, sname in ((1, "Over"), (-1, "Under")):
                    for flag in (1.0, 0.0):
                        x = Bt[(Bt.best_side == side) & (Bt[col] == flag)]
                        bet_rows.append({"idea": label, "era": era, "side": sname, "flagged": bool(flag), "bets": len(x),
                                         "won": x.won.mean(), "ROI @-110": (x.won * 100 / 110 - (1 - x.won)).mean()})
        d, v = rec["t all games (disc)"], rec["t all games (val)"]
        rec["lead?"] = bool(np.isfinite(d) and np.isfinite(v) and abs(d) >= 2 and abs(v) >= 1.5 and np.sign(d) == np.sign(v))
        rec["direction as expected?"] = bool(d < 0) if rec["lead?"] else None
        rows.append(rec)
    S = pd.DataFrame(rows)
    lines = ["# Loss autopsy, round 3: absences known before the opener (NCAAB, 2011-21; 2021-26 not read)\n",
             "A key player = 25+ minutes a game over his team's five games before the last one. Only earlier box "
             "scores are used, so everything here is known when the opener is posted.\n",
             "How often a key player who sat out sits again in the next game: "
             + "; ".join(f"{k}: {v[1]:.0%} of {v[0]:,}" for k, v in persist.items()) + ".\n",
             df_to_md(S, "{:.2f}"), "",
             "Bets with and without the flag:\n", df_to_md(pd.DataFrame(bet_rows), "{:.3f}"), ""]
    (ROOT / "reports" / "loss_autopsy_round3.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("loss_autopsy_round3", {"key_min": KEY_MIN, "prev_games": PREV_GAMES, "rule": "|t|>=2 disc and |t|>=1.5 same sign val"},
                   {"ideas": S.to_dict("records"), "persistence": persist})


if __name__ == "__main__":
    main()
