"""Loss autopsy and creative-edge screen for the NCAAB straight bets (locked v3, P >= 55% at the opener).

Part 1 — why bets lost. Every bet's miss is split, after the game, into what moved the total away
from the line: overtime, 3-point shooting against the league rate, free-throw shooting, 2-point
shooting, and pace (possessions against the engine's own forecast). Losses that are pure shooting
luck cannot be forecast; anything structural is a lead.

Part 2 — pre-game ideas, each turned into something knowable before tip-off and screened for whether
it predicts the miss (total - opener - engine forecast) on every game and whether it changes the
bets' win rate. Rule, fixed before running: an idea is a lead if |t| >= 2 in the discovery seasons
(2011-12..2017-18) AND it points the same way with |t| >= 1.5 in the validation seasons
(2018-19..2020-21). The 2021-26 seasons are not read here; they are kept for a one-time check of
any lead turned into a rule.
Writes reports/loss_autopsy.md and data/processed/loss_autopsy_bets.parquet.
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

from backtest.analysis import df_to_md
from backtest.wf2 import main_line_probs
from config_loader import ROOT, log_experiment
from diagnose_bets import load

DISC = [f"{y}-{str(y + 1)[2:]}" for y in range(2011, 2018)]
VAL = [f"{y}-{str(y + 1)[2:]}" for y in range(2018, 2021)]
ERA = {**{s: "discovery 2011-18" for s in DISC}, **{s: "validation 2018-21" for s in VAL}}
P_MIN = 0.55
HIGH_ALT = {"laramie", "fort collins", "colorado springs", "albuquerque", "logan", "provo", "salt lake city", "ogden",
            "orem", "cedar city", "boulder", "denver", "greeley", "bozeman", "reno", "flagstaff", "pocatello"}
TZ = {**{s: -5 for s in "CT DE DC FL GA IN MA MD ME MI NC NH NJ NY OH PA RI SC VA VT WV KY".split()},
      **{s: -6 for s in "AL AR IA IL KS LA MN MO MS ND NE OK SD TN TX WI".split()},
      **{s: -7 for s in "AZ CO ID MT NM UT WY".split()}, **{s: -8 for s in "CA NV OR WA".split()},
      "AK": -9, "HI": -10, "PR": -4}


def schedules() -> pd.DataFrame:
    import glob

    import pyarrow.parquet as pq
    cols = ["game_id", "game_date_time", "venue_address_city", "venue_address_state", "home_id", "away_id", "neutral_site"]
    frames = []
    for f in sorted(glob.glob(str(ROOT / "data" / "raw" / "ncaab" / "mbb_schedule_*.parquet"))):
        have = set(pq.read_schema(f).names)
        frames.append(pd.read_parquet(f, columns=[c for c in cols if c in have]))
    s = pd.concat(frames, ignore_index=True).drop_duplicates("game_id")
    s["city"] = s.venue_address_city.fillna("").str.strip().str.lower()
    s["state"] = s.venue_address_state.fillna("").str.strip().str.upper()
    return s


def team_home_tz(s: pd.DataFrame) -> dict:
    home = s[~s.neutral_site.astype(bool)].groupby("home_id").state.agg(lambda x: x.mode().iloc[0] if len(x.mode()) else "")
    return {f"e{k}": TZ.get(v, -5) for k, v in home.items()}


def pregame_features(P: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    """Ideas knowable before tip-off, computed from earlier games only."""
    G = P.sort_values(["date", "game_key"]).copy()
    # rematches: earlier meetings of the same two teams this season, and how the last one went vs its close
    G["pair"] = np.where(G.home < G.away, G.home + "|" + G.away, G.away + "|" + G.home)
    G["meeting"] = G.groupby(["season", "pair"]).cumcount() + 1
    G["resid_close"] = G.outcome - G.line_close
    G["prev_meet_resid"] = G.groupby(["season", "pair"]).resid_close.shift(1)
    # recency: each team's previous game, total vs its closing line
    long = pd.concat([G[["game_key", "date", "season", "home", "resid_close"]].rename(columns={"home": "team"}),
                      G[["game_key", "date", "season", "away", "resid_close"]].rename(columns={"away": "team"})])
    long = long.sort_values(["team", "date"])
    long["last_resid"] = long.groupby(["team", "season"]).resid_close.shift(1)
    last = long.set_index(["game_key", "team"]).last_resid
    G["last_resid_sum"] = (last.reindex(pd.MultiIndex.from_arrays([G.game_key, G.home])).values
                           + last.reindex(pd.MultiIndex.from_arrays([G.game_key, G.away])).values)
    # venue, tip time and body clock (from the ESPN schedule)
    sch = s.set_index("game_id")
    gid = G.espn_game_id
    G["city"] = gid.map(sch.city)
    G["high_altitude"] = G.city.isin(HIGH_ALT).astype(float).where(G.city.notna())
    tip = gid.map(sch.game_date_time)
    tz = team_home_tz(s)
    et_hour = pd.to_datetime(tip).dt.hour + pd.to_datetime(tip).dt.minute / 60
    G["away_body_clock"] = et_hour + (G.away.map(tz).fillna(-5) + 5)      # tip time on the away team's home clock
    G["early_for_away"] = (G.away_body_clock < 13).astype(float).where(et_hour.notna())
    G["late_for_away"] = (G.away_body_clock >= 21).astype(float).where(et_hour.notna())
    G["tz_shift"] = (G.home.map(tz).fillna(-5) - G.away.map(tz).fillna(-5)).abs()
    return G


def decompose(B: pd.DataFrame, box: pd.DataFrame) -> pd.DataFrame:
    """Post-game split of each bet's miss (positive = helped the bet)."""
    b = box[box.box_ok].copy()
    b["fg2m"], b["fg2a"] = b.fgm - b.fg3m, b.fga - b.fg3a
    g = b.groupby("espn_game_id").agg(fg3m=("fg3m", "sum"), fg3a=("fg3a", "sum"), ftm=("ftm", "sum"), fta=("fta", "sum"),
                                      fg2m=("fg2m", "sum"), fg2a=("fg2a", "sum"), poss=("poss", "first"),
                                      season=("espn_season", "first"))
    rates = b.groupby("espn_season")[["fg3m", "fg3a", "ftm", "fta", "fg2m", "fg2a"]].sum()
    L3, LFT, L2 = rates.fg3m / rates.fg3a, rates.ftm / rates.fta, rates.fg2m / rates.fg2a
    g["three_luck"] = 3 * (g.fg3m - g.fg3a * g.season.map(L3))
    g["ft_luck"] = g.ftm - g.fta * g.season.map(LFT)
    g["two_luck"] = 2 * (g.fg2m - g.fg2a * g.season.map(L2))
    X = B.join(g[["three_luck", "ft_luck", "two_luck", "poss"]], on="espn_game_id", rsuffix="_box")
    reg = X.home_1h + X.away_1h + X.home_2h_reg + X.away_2h_reg
    X["ot_pts"] = (X.outcome - reg).clip(lower=0)
    X["pace_pts"] = (X.poss_box - X.rt_poss) * (X.line / X.rt_poss)
    sgn = X.best_side
    for c in ("ot_pts", "three_luck", "ft_luck", "two_luck", "pace_pts"):
        X[f"s_{c}"] = sgn * X[c]
    X["s_miss"] = sgn * (X.outcome - X.line)
    return X


def t_stat(x, y):
    """t of the slope of y on x (both arrays; NaNs dropped)."""
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m] - x[m].mean(), y[m]
    if len(x) < 30 or (x ** 2).sum() == 0:
        return np.nan, int(m.sum())
    b = (x * y).sum() / (x ** 2).sum()
    res = y - y.mean() - b * x
    return float(b / np.sqrt((res ** 2).sum() / (len(y) - 2) / (x ** 2).sum())), int(m.sum())


def main():
    from data.ncaab_unify import load_all_box
    P, cals, _ = load()
    P = P[P.season.isin(ERA)]
    M = main_line_probs(P, cals)
    M = M[M.eligible].copy()
    M["era"] = M.season.map(ERA)
    s = schedules()
    G = pregame_features(M, s)
    G["r"] = G.outcome - G.line - G.mu                       # miss against the engine's own forecast
    G["bet"] = (G.p_best >= P_MIN) & ~G.best_push
    G["won"] = G.best_win.astype(int)

    # ---------------- part 1: why bets lost
    B = decompose(G[G.bet], load_all_box())
    have = B.s_three_luck.notna() & B.s_ot_pts.notna() & B.pace_pts.notna()
    parts = ["s_three_luck", "s_two_luck", "s_ft_luck", "s_pace_pts", "s_ot_pts"]
    names = {"s_three_luck": "3-point shooting vs league rate", "s_two_luck": "2-point shooting vs league rate",
             "s_ft_luck": "free-throw shooting vs league rate", "s_pace_pts": "pace vs the engine's forecast",
             "s_ot_pts": "overtime points"}
    rows = []
    for era in list(dict.fromkeys(ERA.values())):
        for res, lab in ((1, "won"), (0, "lost")):
            x = B[have & (B.era == era) & (B.won == res)]
            rows.append({"era": era, "bets": lab, "n": len(x), "points beaten by (+) / missed by (-)": x.s_miss.mean(),
                         **{names[c]: x[c].mean() for c in parts}})
    A = pd.DataFrame(rows)
    lost = B[have & (B.won == 0)]
    main_cause = lost[parts].idxmin(axis=1).map(names)
    cause = (main_cause.value_counts(normalize=True) * 100).round(1).rename("share of losses where it hurt most (%)")
    lost_by_side = lost.assign(side=np.where(lost.best_side == 1, "Over", "Under")).groupby("side")[parts + ["s_miss"]].mean()
    lost_by_side.columns = [names.get(c, "missed by") for c in lost_by_side.columns]
    ot_lost = float((lost.ot_pts > 0).mean())
    ot_lost_under = float((lost[lost.best_side == -1].ot_pts > 0).mean())

    # ---------------- part 2: pre-game ideas
    G["close_game"] = (G.abs_spread <= 3).astype(float)
    G["blowout_expected"] = (G.abs_spread >= 18).astype(float)
    G["second_meeting_plus"] = (G.meeting >= 2).astype(float)
    G["third_meeting_plus"] = (G.meeting >= 3).astype(float)
    ideas = {
        "rematch (2nd+ meeting this season)": "second_meeting_plus",
        "3rd+ meeting (conference tournament rematches)": "third_meeting_plus",
        "last meeting beat its closing total by more": "prev_meet_resid",
        "both teams' last game beat its closing total by more": "last_resid_sum",
        "early tip on the away team's body clock (< 1 pm)": "early_for_away",
        "late tip on the away team's body clock (9 pm+)": "late_for_away",
        "time zones crossed by the away team": "tz_shift",
        "high-altitude venue": "high_altitude",
        "close game expected (spread 3 or less)": "close_game",
        "blowout expected (spread 18+)": "blowout_expected",
        "3-point-heavy matchup (style)": "m_tpar",
        "opening total (level)": "line",
    }
    rows = []
    for label, col in ideas.items():
        rec = {"idea": label}
        for era in list(dict.fromkeys(ERA.values())):
            E = G[G.era == era]
            t_all, n_all = t_stat(E[col].values.astype(float), E.r.values.astype(float))
            Bt = E[E.bet]
            # for bets: does the idea move the bet's own result? signed miss = side x (total - line)
            t_bet, n_bet = t_stat(Bt[col].values.astype(float), (Bt.best_side * (Bt.outcome - Bt.line)).values.astype(float))
            short = "disc" if era.startswith("disc") else "val"
            rec[f"t all games ({short})"] = t_all
            rec[f"t our bets ({short})"] = t_bet
            rec[f"n games ({short})"] = n_all
        d, v = rec["t all games (disc)"], rec["t all games (val)"]
        rec["lead?"] = bool(np.isfinite(d) and np.isfinite(v) and abs(d) >= 2 and abs(v) >= 1.5 and np.sign(d) == np.sign(v))
        rows.append(rec)
    S = pd.DataFrame(rows)

    # side-specific checks of the two structural mechanisms (close games -> fouling/OT; blowouts -> bench minutes)
    side_rows = []
    for era in list(dict.fromkeys(ERA.values())):
        Bt = G[G.bet & (G.era == era)]
        for side, sname in ((1, "Over"), (-1, "Under")):
            for col, lab in (("close_game", "close game expected"), ("blowout_expected", "blowout expected")):
                for v in (1.0, 0.0):
                    x = Bt[(Bt.best_side == side) & (Bt[col] == v)]
                    if len(x):
                        side_rows.append({"era": era, "side": sname, "game type": lab if v == 1 else "other games",
                                          "check": lab, "bets": len(x), "won": x.won.mean(),
                                          "ROI @-110": (x.won * 100 / 110 - (1 - x.won)).mean()})
    SS = pd.DataFrame(side_rows)

    lines = ["# Loss autopsy and creative-edge screen (NCAAB straight bets, 2011-21; 2021-26 not read)\n",
             "## 1. Why the bets lost\n",
             "After each game, its total is split into what pushed it away from the line. Positive numbers helped the "
             "bet, negative hurt it (points; shooting is measured against that season's league averages, pace against the "
             "engine's own possession forecast). Games with a box score only.\n",
             df_to_md(A, "{:.2f}"), "",
             "Lost bets by side (average points each factor cost):\n", df_to_md(lost_by_side.reset_index(), "{:.2f}"), "",
             "Which factor hurt most in each lost bet:\n", df_to_md(cause.reset_index().rename(columns={"index": "factor"}), "{:.1f}"), "",
             f"Overtime happened in {ot_lost:.1%} of all lost bets and {ot_lost_under:.1%} of lost Unders.\n",
             "## 2. Pre-game ideas\n",
             "t = how strongly the idea predicts the miss against the engine's forecast (all games) and the bets' own "
             "margin (our bets). A lead needs |t| >= 2 in discovery and the same sign with |t| >= 1.5 in validation "
             "(rule fixed before running).\n",
             df_to_md(S, "{:.2f}"), "",
             "Close-game and blowout checks, by side:\n", df_to_md(SS, "{:.3f}"), ""]
    (ROOT / "reports" / "loss_autopsy.md").write_text("\n".join(lines) + "\n")
    B.to_parquet(ROOT / "data" / "processed" / "loss_autopsy_bets.parquet", index=False)
    print("\n".join(lines))
    log_experiment("loss_autopsy", {"eras": {"discovery": DISC, "validation": VAL}, "rule": "|t|>=2 disc and |t|>=1.5 same sign val"},
                   {"ideas": S.to_dict("records"), "causes": cause.to_dict()})


if __name__ == "__main__":
    main()
