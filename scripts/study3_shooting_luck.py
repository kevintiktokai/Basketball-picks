"""Improvement study 3 — shooting-luck-neutral ratings (pre-registered: config/improvements.yaml `study_3`).

Every game is re-scored with the league's season-to-date 3P% and FT% (shot volumes kept), a second
set of daily ratings is fitted on those points, and the locked v3 mean model gets two extra
features (neutral ratings total - opener, points and efficiency versions). Selection on 2011-21;
the candidate, if it qualifies, is checked ONCE on the sealed 2021-26 seasons.
Writes reports/study3_shooting_luck.md.
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
import yaml

import study2_stage_matchup as S2
from backtest.analysis import df_to_md
from config_loader import ROOT, log_experiment
from features.ratings import DailyRatings
from stage3_common import evaluate

CFG = yaml.safe_load((ROOT / "config" / "improvements.yaml").read_text())["study_3"]
REPORT = ROOT / "reports" / "study3_shooting_luck.md"
EXTRA = {"L1_shooting_neutral": ["x_pts_n", "x_eff_n"]}
RATINGS_KW = {"half_life_days": 45, "prev_season_weight": 0.15, "ridge": 3.0}   # as the engine's features
MIN_ATTEMPTS = 5000
FIRST_SEASON_RATES = (0.34, 0.69)        # only for the first scraped season's opening weeks (training only)


def league_rates(box: pd.DataFrame) -> pd.DataFrame:
    """League 3P% and FT% by (season, date), using only earlier dates of the season; the previous
    season's full rate until the season has MIN_ATTEMPTS attempts."""
    b = box[box.box_ok]
    day = b.groupby(["espn_season", "date"])[["fg3m", "fg3a", "ftm", "fta"]].sum().sort_index()
    before = day.groupby(level=0).cumsum() - day
    full = day.groupby(level=0).sum()
    prev = full.shift(1)
    out = pd.DataFrame(index=day.index)
    for made, att, k in (("fg3m", "fg3a", 0), ("ftm", "fta", 1)):
        own = before[made] / before[att].where(before[att] > 0)
        p = (prev[made] / prev[att]).reindex(day.index.get_level_values(0)).values
        p = np.where(np.isnan(p), FIRST_SEASON_RATES[k], p)
        out["L3" if k == 0 else "LFT"] = np.where(before[att].values >= MIN_ATTEMPTS, own.values, p)
    return out.reset_index()


def neutral_points(box: pd.DataFrame) -> pd.Series:
    """Points with league-average 3P% and FT%, keyed by (espn_game_id, team_id)."""
    b = box[box.box_ok].merge(league_rates(box), on=["espn_season", "date"], how="left")
    pts_n = 2 * (b.fgm - b.fg3m) + 3 * b.fg3a * b.L3 + b.fta * b.LFT
    return pd.Series(pts_n.values, index=pd.MultiIndex.from_arrays([b.espn_game_id.astype("int64"),
                                                                    b.team_id.astype("int64")]))


def neutral_ratings(u: pd.DataFrame, box: pd.DataFrame, fp: str) -> pd.DataFrame:
    from features.store import STORE
    path = STORE / f"ncaab_neutral_ratings_{fp}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    g = u[u.clean].copy()
    poss = box[box.box_ok].drop_duplicates("espn_game_id").set_index("espn_game_id").poss
    g["poss"] = g.espn_game_id.map(poss)
    pn = neutral_points(box)
    for side in ("home", "away"):
        ok = g.espn_game_id.notna() & g[f"espn_{side}_id"].notna()
        key = pd.MultiIndex.from_arrays([g.loc[ok, "espn_game_id"].astype("int64"),
                                         g.loc[ok, f"espn_{side}_id"].astype("int64")])
        val = pn.reindex(key).values
        g[f"{side}_pts"] = g[f"{side}_pts"].astype(float)
        g.loc[ok, f"{side}_pts"] = np.where(np.isnan(val), g.loc[ok, f"{side}_pts"], val)   # no box: real points
    r = DailyRatings(**RATINGS_KW).run(g)
    r = r[["game_key", "rt_pts_home", "rt_pts_away", "rt_eff_total"]].rename(
        columns={"rt_pts_home": "rt_pts_home_n", "rt_pts_away": "rt_pts_away_n", "rt_eff_total": "rt_eff_total_n"})
    r.to_parquet(path, index=False)
    return r


def market():
    from data.ncaab_unify import unify
    from features.ncaab_features import market_frame
    from features.store import fingerprint, get_features
    u, box, _ = unify(write=False, include_live=True)
    fp = fingerprint(u, box)
    f = get_features("ncaab", u, box, verbose=False)
    d = market_frame(f, "open")
    d = d.merge(neutral_ratings(u, box, fp), on="game_key", how="left")
    d["x_pts_n"] = d.rt_pts_home_n + d.rt_pts_away_n - d.line
    d["x_eff_n"] = d.rt_eff_total_n - d.line
    return d.reset_index(drop=True), fp


def main():
    if REPORT.exists():
        sys.exit(f"REFUSING: {REPORT.name} exists — study 3's confirmation on 2021-26 runs once only.")
    from features.store import cached_walk_forward
    d, fp = market()
    seasons = sorted(d.season.unique())
    base_spec = S2.spec_v3()
    arms = {"locked_v3": cached_walk_forward(d, base_spec, seasons, fp)}
    for name, extra in EXTRA.items():
        spec = dict(base_spec, mean_feats=list(base_spec["mean_feats"]) + extra, study="study_3:" + name)
        arms[name] = cached_walk_forward(d, spec, seasons, fp)
    Ms = {k: S2.main_line(P, cals) for k, (P, cals, _) in arms.items()}
    base = Ms["locked_v3"]
    n_by_season = base[base.p_best >= S2.P_MIN].groupby("season").size().to_dict()

    rows = []
    for name, M in Ms.items():
        for era, ss in S2.SEL_ERAS.items():
            rows.append({"engine": name, "era": era, **S2.era_metrics(M, n_by_season, ss)})
        rows.append({"engine": name, "era": "2011-21", **S2.era_metrics(M, n_by_season, S2.DEV + S2.HOLD)})
    S = pd.DataFrame(rows)
    b = S[S.engine == "locked_v3"].set_index("era")
    qual = {}
    for name in EXTRA:
        c = S[S.engine == name].set_index("era")
        qual[name] = bool(all(c.loc[e, "log loss"] < b.loc[e, "log loss"] and
                              c.loc[e, "matched ROI @-110"] > b.loc[e, "matched ROI @-110"] for e in S2.SEL_ERAS))
    ok = [n for n in EXTRA if qual[n]]
    selected = ok[0] if ok else None
    corr = d[d.season.isin(S2.DEV + S2.HOLD)][["x_pts", "x_pts_n", "x_eff", "x_eff_n"]].corr().round(3)

    lines = ["# Improvement study 3 — shooting-luck-neutral ratings (NCAAB)\n",
             "_Pre-registered in `config/improvements.yaml` (`study_3`) before the candidate was fitted. "
             "Selection on 2011-21 only; a qualifying candidate is checked once on the sealed 2021-26 seasons._\n",
             "How similar the new features are to the engine's (2011-21 correlations):\n", df_to_md(corr.reset_index()), "",
             "## Selection (2011-21)\n", df_to_md(S, "{:.4f}"), "",
             "Qualifies (lower log loss AND higher matched ROI in both eras): "
             + ", ".join(f"{n} **{q}**" for n, q in qual.items()) + f". Selected: **{selected or 'none'}**.\n"]
    verdict = None
    if selected:
        books = d.set_index("game_key").books_json
        C = pd.DataFrame([{"engine": n, **S2.era_metrics(Ms[n], n_by_season, S2.CONF, real=True)}
                          for n in ("locked_v3", selected)]).set_index("engine")
        c, l = C.loc[selected], C.loc["locked_v3"]
        verdict = bool(c["log loss"] < l["log loss"] and c["matched ROI @-110"] >= l["matched ROI @-110"]
                       and c["matched ROI real price"] >= l["matched ROI real price"])
        cards = []
        for name in ("locked_v3", selected):
            P, cals, calm = arms[name]
            R, _ = evaluate(P, cals, calm, books, S2.CONF)
            R = R[(R.season == "POOLED") & R["product"].str.match(r"(TARGET|MAIN)")]
            cards += [{"engine": name, "product": x["product"].split(" (")[0], "cards": x.cards, "hit": x.hit,
                       "leg_win": x.leg_win, "roi": x.roi, "roi_ci95": x.roi_ci95} for _, x in R.iterrows()]
        lines += ["## Confirmation on the sealed 2021-26 seasons (run once)\n", df_to_md(C.reset_index(), "{:.4f}"), "",
                  "2.5+ target cards and main-line doubles at real prices, 2021-26:\n",
                  df_to_md(pd.DataFrame(cards), "{:.3f}"), "",
                  f"**Confirmation passed: {verdict}** (lower log loss, matched ROI not lower at -110 and at the "
                  "best real price)."]
        if verdict:
            path = ROOT / "config" / "improvements_adopted.yaml"
            cur = yaml.safe_load(path.read_text()) if path.exists() else {}
            cur["study_3"] = {"adopted": selected, "extra_mean_feats": EXTRA[selected],
                              "use": "2026-27 forward ledger: recorded next to the locked v3 engine"}
            path.write_text(yaml.safe_dump(cur, sort_keys=False))
    else:
        lines.append("No candidate qualified, so the 2021-26 seasons stay sealed.")
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("study3_shooting_luck", {"pre_registration": CFG, "extra": EXTRA},
                   {"selection": S.to_dict("records"), "qualifies": qual, "selected": selected, "confirmed": verdict})


if __name__ == "__main__":
    main()
