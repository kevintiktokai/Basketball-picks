"""NCAAB straight bets: can the locked engine bet more often without losing its edge?

Decision-layer rules only (the model is unchanged), each judged by profit per season, not win rate:
  * a lower probability bar at the opener (55% is the current rule);
  * the best N games of each day by probability, above a floor (volume no longer depends on how far
    the engine leans away from the openers, which is what dried up in 2024-26);
  * everything at 55%+ plus the best of the rest up to N a day;
  * line shopping (2021-26 only, where per-book openers exist): each game judged at the best opening
    line on offer for each side, not at the consensus opener.
Rules are chosen on 2011-21 at -110 (the engine was built and checked on those seasons); 2021-26 at
real best-book prices is shown as a re-analysis (those seasons were scored once already), so a
rule picked here still needs a forward test.
Writes reports/volume_study.md.
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
from backtest.odds_cards import best_main
from backtest.wf2 import Z95, main_line_probs
from config_loader import ROOT, log_experiment
from diagnose_bets import load

DEV = [f"{y}-{str(y + 1)[2:]}" for y in range(2011, 2021)]
TEST = [f"{y}-{str(y + 1)[2:]}" for y in range(2021, 2026)]
ODDS_110 = 1 + 100 / 110


def frame() -> pd.DataFrame:
    P, cals, _ = load()
    M = main_line_probs(P, cals)
    M = M[M.eligible & M.season.isin(DEV + TEST)].copy()
    M["day"] = M.date.dt.strftime("%Y-%m-%d")
    # real best-book line and price for each side, and the engine's probability at that line
    for side, name in ((1, "over"), (-1, "under")):
        st = [best_main(bj, side)[:2] if isinstance(bj, str) and bj.startswith("{") else (np.nan, np.nan)
              for bj in M.books_json]
        M[f"line_{name}"], M[f"odds_{name}"] = np.array(st, dtype=float).T
        thr = np.where(side == 1, np.ceil(M[f"line_{name}"] + 0.5) - 0.5, np.floor(M[f"line_{name}"] - 0.5) + 0.5)
        p = np.full(len(M), np.nan)
        ok = M[f"line_{name}"].notna().values
        for season, idx in M[ok].groupby("season").groups.items():
            ii = M.index.get_indexer(idx)
            sm = side * M.mu.values[ii] / M.sd.values[ii]
            sb = side * (M.line.values[ii] - thr[ii]) / M.sd.values[ii]
            p[ii] = cals[season].prob(sm, sb, z=Z95, side=side)[0]
        M[f"p_{name}_shop"] = p
    return M


def grade(B: pd.DataFrame, side, line, odds) -> pd.DataFrame:
    win = np.where(side == 1, B.outcome > line, B.outcome < line)
    push = B.outcome.values == line
    return B.assign(pnl=np.where(push, 0.0, np.where(win, odds - 1, -1.0)), won=win & ~push, push=push)


def at_opener(B: pd.DataFrame, real: bool) -> pd.DataFrame:
    """The engine's side at the consensus opener; real = that side's best book line and price."""
    side = B.best_side.values
    if real:
        rl = np.where(side == 1, B.line_over, B.line_under)
        ro = np.where(side == 1, B.odds_over, B.odds_under)
        ok = ~np.isnan(rl) & ~np.isnan(ro)
        return grade(B, side, np.where(ok, rl, B.line), np.where(ok, ro, ODDS_110))
    return grade(B, side, B.line.values, np.full(len(B), ODDS_110))


def top_n(M: pd.DataFrame, n: int, floor: float, keep_all: float | None = None) -> pd.DataFrame:
    """Each day's n most probable picks above `floor`; with keep_all, every pick at or above it too."""
    E = M[M.p_best >= floor].sort_values(["day", "p_best"], ascending=[True, False])
    rank = E.groupby("day").cumcount()
    keep = rank < n
    if keep_all is not None:
        keep |= E.p_best >= keep_all
    return E[keep]


def shopped(M: pd.DataFrame, floor: float) -> pd.DataFrame:
    """Line shopping: the side whose best line on offer gives the higher value, if its P clears floor."""
    S = M[M.p_over_shop.notna() & M.p_under_shop.notna()].copy()
    v_o, v_u = S.p_over_shop * S.odds_over, S.p_under_shop * S.odds_under
    side = np.where(v_o >= v_u, 1, -1)
    S["p_shop"] = np.where(side == 1, S.p_over_shop, S.p_under_shop)
    S = S.assign(side_shop=side)
    S = S[S.p_shop >= floor]
    return grade(S, S.side_shop.values, np.where(S.side_shop == 1, S.line_over, S.line_under),
                 np.where(S.side_shop == 1, S.odds_over, S.odds_under))


def season_table(G: pd.DataFrame, seasons: list) -> pd.DataFrame:
    g = G[G.season.isin(seasons)].groupby("season")
    T = pd.DataFrame({"bets": g.size(), "units": g.pnl.sum()}).reindex(seasons).fillna(0)
    return T


def summarise(name: str, G: pd.DataFrame, seasons: list) -> dict:
    T = season_table(G, seasons)
    dec = G[~G.push & G.season.isin(seasons)]
    daily = G[G.season.isin(seasons)].groupby("day").pnl.sum().cumsum()
    dd = float((daily.cummax() - daily).max()) if len(daily) else np.nan
    return {"rule": name, "bets a season": T.bets.mean(), "won": dec.won.mean() if len(dec) else np.nan,
            "ROI": G[G.season.isin(seasons)].pnl.mean(), "units a season": T.units.mean(),
            "worst season (units)": T.units.min(), "seasons losing": int((T.units < 0).sum()),
            "deepest dip (units)": dd}


def main():
    M = frame()
    rules = {}
    for thr in (0.55, 0.545, 0.54, 0.535, 0.53, 0.525):
        rules[f"P >= {thr:.1%}"] = lambda R, real, t=thr: at_opener(R[R.p_best >= t], real)
    for n in (3, 5, 8):
        for floor in (0.53, 0.525):
            rules[f"best {n} a day, P >= {floor:.1%}"] = lambda R, real, n=n, f=floor: at_opener(top_n(R, n, f), real)
    for n in (3, 5):
        rules[f"all at 55% + best of rest to {n} a day (P >= 53%)"] = (
            lambda R, real, n=n: at_opener(top_n(R, n, 0.53, keep_all=0.55), real))

    dev_rows, test_rows, per_season = [], [], {}
    for name, f in rules.items():
        Gd = f(M[M.season.isin(DEV)], real=False)
        Gt = f(M[M.season.isin(TEST)], real=True)
        dev_rows.append(summarise(name, Gd, DEV))
        test_rows.append(summarise(name, Gt, TEST))
        per_season[name] = pd.concat([season_table(Gd, DEV), season_table(Gt, TEST)])
    for floor in (0.55, 0.54, 0.53):
        name = f"line shopping, P >= {floor:.0%} at the best line"
        Gt = shopped(M[M.season.isin(TEST)], floor)
        test_rows.append(summarise(name, Gt, TEST))
        per_season[name] = pd.concat([pd.DataFrame(index=DEV, columns=["bets", "units"]), season_table(Gt, TEST)])
    D, T = pd.DataFrame(dev_rows), pd.DataFrame(test_rows)

    # choose on 2011-21: most units a season with ROI >= 5% and no worse a worst season than the current rule
    cur = D[D.rule == "P >= 55.0%"].iloc[0]
    ok = D[(D.ROI >= 0.05) & (D["worst season (units)"] >= cur["worst season (units)"] - 10)]
    pick = ok.sort_values("units a season", ascending=False).iloc[0].rule

    show = [r for r in ["P >= 55.0%", pick, "P >= 53.0%", "best 5 a day, P >= 53.0%",
                        "all at 55% + best of rest to 5 a day (P >= 53%)", "line shopping, P >= 54% at the best line"]
            if r in per_season]
    S = pd.DataFrame({r: per_season[r].units for r in dict.fromkeys(show)}).round(1)
    V = pd.DataFrame({r: per_season[r].bets for r in dict.fromkeys(show)})
    S.index.name = V.index.name = "season"

    lines = ["# NCAAB straight bets: more volume without losing the edge?\n",
             "Locked v3 engine, unchanged; only the betting rule varies. 1 unit = one flat stake. "
             "2011-21 at -110 (where a rule is chosen); 2021-26 at each side's best real opening line and price "
             "(re-analysis: those seasons were already scored once).\n",
             "## 2011-21 (choose here)\n", df_to_md(D, "{:,.3f}"), "",
             f"Chosen on 2011-21 (most units a season with ROI of 5%+ and a worst season no more than 10 units "
             f"below the current rule's): **{pick}**.\n",
             "## 2021-26 at real prices (check)\n", df_to_md(T, "{:,.3f}"), "",
             "## Units won by season\n", df_to_md(S.reset_index(), "{:,.1f}"), "",
             "## Bets by season\n", df_to_md(V.reset_index(), "{:,.0f}"), ""]
    (ROOT / "reports" / "volume_study.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("volume_study", {"rules": list(rules), "pick": pick},
                   {"dev": dev_rows, "test": test_rows})


if __name__ == "__main__":
    main()
