"""What does the free official EuroLeague / EuroCup data add to a totals model?

Point-in-time throughout: team ratings, referee tendencies and rest use only games on
EARLIER dates. No odds are used (no free historical feed has been verified yet), so this
measures whether information exists beyond team strength, not whether the market prices it.

Evaluation is walk-forward: each season from 2019-20 is predicted by a model fitted only on
earlier seasons (2016-18 warm up the ratings and referee histories).
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
from data.euroleague import parse
from features.ratings import DailyRatings

CODES = [f"{c}{y}" for c in ("E", "U") for y in range(2016, 2026)]
HL_GAMES = 25.0          # referee memory (games)
SHRINK = 15.0            # pseudo-games of "average referee"
FIRST_EVAL = "2019-20"
FIRST_TRAIN = "2017-18"
FEATS = ["crew_fta", "crew_pf", "crew_resid", "short_rest_home", "short_rest_away"]


def referee_tendencies(G: pd.DataFrame, col: str) -> pd.Series:
    """Crew tendency for `col` (a per-game deviation), from each referee's PRIOR games only."""
    long = pd.concat([G[["game_key", "date", r, col]].rename(columns={r: "ref"}) for r in ("ref1", "ref2", "ref3")])
    long = long.dropna(subset=["ref"]).sort_values(["ref", "date"])
    decay = 0.5 ** (1 / HL_GAMES)
    vals = {}
    for ref, grp in long.groupby("ref"):
        m, w = 0.0, 0.0
        last_date, pending = None, []
        for row in grp.itertuples(index=False):
            if last_date is not None and row.date != last_date:     # fold in earlier dates only
                for x in pending:
                    if not np.isnan(x):
                        m = (m * w * decay + x) / (w * decay + 1)
                        w = w * decay + 1
                pending = []
            vals[(row.game_key, ref)] = m * w / (w + SHRINK)      # shrunk toward 0 (= average)
            pending.append(getattr(row, col))
            last_date = row.date
    crew = long.assign(t=[vals[(k, r)] for k, r in zip(long.game_key, long.ref)])
    return crew.groupby("game_key").t.mean()


def rest_days(G: pd.DataFrame) -> pd.DataFrame:
    """Days since each team's previous game in the same competition (domestic games unseen)."""
    long = pd.concat([G[["game_key", "competition", "date", s]].rename(columns={s: "team"}).assign(side=s)
                      for s in ("home", "away")]).sort_values(["competition", "team", "date"])
    long["rest"] = long.groupby(["competition", "team"]).date.diff().dt.days
    return long.pivot(index="game_key", columns="side", values="rest")


def build() -> pd.DataFrame:
    G, B = parse(CODES)
    G = G.sort_values("date").reset_index(drop=True)
    tot = B.groupby("game_key").agg(fta=("fta", "sum"), pf=("pf", "sum"), poss=("poss", "first"))
    G = G.merge(tot, on="game_key", how="left")
    G["neutral"] = G["round"].eq("FF")                         # EuroLeague Final Four
    parts = []
    for comp, Gc in G.groupby("competition"):
        r = DailyRatings(half_life_days=60, prev_season_weight=0.25, ridge=3.0, venue_tempo=True).run(
            Gc[["date", "season", "home", "away", "neutral", "home_pts", "away_pts", "poss", "game_key"]])
        Gc = Gc.merge(r, on="game_key", how="left")
        daily = Gc.groupby("date")[["fta", "pf"]].mean()
        trail = daily.rolling(60, min_periods=5).mean().shift(1)   # earlier game dates only
        Gc["fta_dev"] = Gc.fta - Gc.date.map(trail.fta)
        Gc["pf_dev"] = Gc.pf - Gc.date.map(trail.pf)
        parts.append(Gc)
    G = pd.concat(parts).sort_values("date").reset_index(drop=True)
    G["exp_total"] = G.rt_eff_total.fillna(G.rt_pts_home + G.rt_pts_away)
    G["resid"] = G.total - G.exp_total
    for col, name in (("fta_dev", "crew_fta"), ("pf_dev", "crew_pf"), ("resid", "crew_resid")):
        G[name] = G.game_key.map(referee_tendencies(G, col))          # pooled across competitions
    R = rest_days(G)
    G["rest_home"], G["rest_away"] = G.game_key.map(R["home"]), G.game_key.map(R["away"])
    G["short_rest_home"] = (G.rest_home <= 2).astype(float)
    G["short_rest_away"] = (G.rest_away <= 2).astype(float)
    G["is_cup"] = G.competition.eq("eurocup").astype(float)
    return G


def ols(X, y):
    A = np.column_stack([np.ones(len(X)), X])
    return np.linalg.lstsq(A, y, rcond=None)[0]


def walk_forward(G: pd.DataFrame):
    D = G[(G.season >= FIRST_TRAIN) & G.exp_total.notna() & G.ref1.notna()].copy()
    D[FEATS] = D[FEATS].fillna(0.0)
    rows, preds = [], []
    for s in sorted(D.season.unique()):
        if s < FIRST_EVAL:
            continue
        tr, te = D[D.season < s], D[D.season == s]
        b0 = ols(tr[["is_cup"]].values, tr.resid.values)
        b1 = ols(tr[["is_cup"] + FEATS].values, tr.resid.values)
        base = b0[0] + b0[1] * te.is_cup.values
        full = b1[0] + te[["is_cup"] + FEATS].values @ b1[1:]
        e0, e1 = ((te.resid - base) ** 2).mean(), ((te.resid - full) ** 2).mean()
        rows.append({"season": s, "games": len(te), "baseline MSE": e0, "with referees+rest MSE": e1,
                     "MSE reduction %": 100 * (1 - e1 / e0)})
        preds.append(te.assign(adj=full - base, target=te.resid - base))
    P = pd.concat(preds)
    e0 = (P.target ** 2).mean()
    e1 = ((P.target - P.adj) ** 2).mean()
    rows.append({"season": "all (out of sample)", "games": len(P), "baseline MSE": e0,
                 "with referees+rest MSE": e1, "MSE reduction %": 100 * (1 - e1 / e0)})
    return pd.DataFrame(rows), P, b1


def main():
    G = build()
    E = G[(G.season >= FIRST_EVAL) & G.exp_total.notna() & G.ref1.notna()].copy()
    E[FEATS] = E[FEATS].fillna(0.0)

    acc = []
    for comp, Ec in E.groupby("competition"):
        sd_season = Ec.groupby("season").total.transform(lambda x: x - x.mean()).std()
        acc.append({"competition": comp, "games": len(Ec), "mean total": Ec.total.mean(),
                    "SD of totals (around season mean)": sd_season, "rating model residual SD": Ec.resid.std(),
                    "rating model MAE": Ec.resid.abs().mean(), "mean residual": Ec.resid.mean()})
    A = pd.DataFrame(acc)

    uni = []
    for name, x in (("crew free-throw tendency", "crew_fta"), ("crew foul tendency", "crew_pf"),
                    ("crew past total-residual", "crew_resid")):
        q = pd.qcut(E[x], 5, labels=False, duplicates="drop")
        top, bot = E[q == q.max()].resid.mean(), E[q == 0].resid.mean()
        uni.append({"feature": name, "corr with game FTA vs average": np.corrcoef(E[x], E.fta_dev.fillna(0))[0, 1],
                    "corr with total residual": np.corrcoef(E[x], E.resid)[0, 1],
                    "top-quintile crews (pts vs expected)": top, "bottom-quintile": bot, "top minus bottom": top - bot})
    for name, x in (("home team on ≤2 days rest", "short_rest_home"), ("away team on ≤2 days rest", "short_rest_away")):
        m = E[x] == 1
        uni.append({"feature": name, "corr with game FTA vs average": np.nan,
                    "corr with total residual": np.corrcoef(E[x], E.resid)[0, 1],
                    "top-quintile crews (pts vs expected)": E[m].resid.mean(), "bottom-quintile": E[~m].resid.mean(),
                    "top minus bottom": E[m].resid.mean() - E[~m].resid.mean()})
    U = pd.DataFrame(uni).rename(columns={"top-quintile crews (pts vs expected)": "group A: pts vs expected",
                                          "bottom-quintile": "group B", "top minus bottom": "A minus B"})

    WF, P, coef = walk_forward(G)
    P["q"] = pd.qcut(P.adj, 5, labels=False)
    Q = P.groupby("q").agg(games=("adj", "size"), predicted_adj=("adj", "mean"), realised=("target", "mean"),
                           over_rate=("target", lambda t: (t > 0).mean())).reset_index()
    Q["q"] = Q.q.map({0: "most Under-leaning 20%", 1: "2nd", 2: "middle", 3: "4th", 4: "most Over-leaning 20%"})

    long = pd.concat([G[["season", r, "fta_dev"]].rename(columns={r: "ref"}) for r in ("ref1", "ref2", "ref3")]).dropna()
    per = long.groupby(["ref", "season"]).fta_dev.agg(["mean", "size"]).reset_index()
    per = per[per["size"] >= 15]
    nxt = per.assign(season=per.season.map(lambda s: f"{int(s[:4]) - 1}-{s[2:4]}"))
    pairs = per.merge(nxt, on=["ref", "season"], suffixes=("", "_next"))
    stab = np.corrcoef(pairs["mean"], pairs["mean_next"])[0, 1] if len(pairs) > 10 else np.nan
    sd_resid = P.target.std()
    spread = Q.realised.iloc[-1] - Q.realised.iloc[0]

    lines = [
        "# What the free EuroLeague / EuroCup data adds (official API, 2016-17 to 2025-26)\n",
        "Point-in-time: ratings, referee tendencies and rest use only earlier dates. **No odds are "
        "used**, so this shows whether information exists beyond team strength, not whether the "
        "market already prices it. Scored seasons: 2019-20 to 2025-26.\n",
        "## 1. Team-rating model accuracy\n", df_to_md(A, "{:.1f}"), "",
        "## 2. Single factors (all games scored, not yet out of sample)\n",
        "Group A/B = top/bottom quintile of the crew feature, or rested vs not.\n",
        df_to_md(U, "{:.3f}"), "",
        f"Referee free-throw tendency is persistent: a referee's season-to-season correlation is "
        f"**{stab:.2f}** (n = {len(pairs)} referee pairs with ≥15 games in consecutive seasons). "
        f"Distinct referees: {pd.concat([G.ref1, G.ref2, G.ref3]).nunique()}.\n",
        "## 3. Out of sample: referees + rest on top of the rating model\n",
        "Each season predicted by a regression fitted only on earlier seasons.\n",
        df_to_md(WF, "{:.2f}"), "",
        "Out-of-sample games grouped by the predicted adjustment (points vs the rating model):\n",
        df_to_md(Q.rename(columns={"q": "group", "predicted_adj": "predicted adj (pts)",
                                   "realised": "actual vs rating model (pts)",
                                   "over_rate": "share above rating model"}), "{:.3f}"), "",
        f"Spread between the most Over- and most Under-leaning fifth: **{spread:+.1f} points** "
        f"(residual SD {sd_resid:.1f}). Near a fair line, 1 point is worth roughly "
        f"{100 * 0.4 / sd_resid:.1f} percentage points of win probability.\n",
        "Fitted on all pre-2025-26 seasons, the coefficients (pts per unit) are: "
        + ", ".join(f"{f} {c:+.2f}" for f, c in zip(["is_cup"] + FEATS, coef[1:])) + ".\n",
    ]
    out = ROOT / "reports" / "euro_info_study.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("euro_info_study", {"codes": CODES, "hl": HL_GAMES, "shrink": SHRINK, "feats": FEATS},
                   {"accuracy": A.to_dict("records"), "walk_forward": WF.to_dict("records"),
                    "quintiles": Q.to_dict("records"), "stability": stab, "n_eval": int(len(P))})


if __name__ == "__main__":
    main()
