"""WNBA games in the same schema as the NCAAB/NBA pipeline, so the identical feature builder,
models, calibrators and card engines apply (stage 3, config/stage3.yaml `wnba`).

  2019..2026 : sportsbookreview.com — real opening/closing totals and spreads, 2-8 books, prices
  box scores : ESPN via sportsdataverse/wehoop-wnba-data (pinned commit), 2018..2026
  2020 is the bubble season (every game at one site), so its games are neutral.
  Preseason games and duplicate SBR records are dropped (exhibition_and_duplicates).
"""
from __future__ import annotations

import hashlib
import urllib.request

import numpy as np
import pandas as pd

from config_loader import ROOT
from data.ncaab_ingest import load_box

PROC = ROOT / "data" / "processed"
WNBA_BOX = ROOT / "data" / "raw" / "wnba_box"
WEHOOP_COMMIT = "a885b8b5834d1937329635cb8c4ba54ffaa09f1e"


def fetch_box(years=range(2018, 2027)) -> list:
    WNBA_BOX.mkdir(parents=True, exist_ok=True)
    out = []
    for y in years:
        dest = WNBA_BOX / f"team_box_{y}.parquet"
        if not dest.exists():
            url = (f"https://raw.githubusercontent.com/sportsdataverse/wehoop-wnba-data/"
                   f"{WEHOOP_COMMIT}/wnba/team_box/parquet/team_box_{y}.parquet")
            urllib.request.urlretrieve(url, dest)
        out.append(dest)
    (WNBA_BOX / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in out))
    return out


def exhibition_and_duplicates(lv: pd.DataFrame, box: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Outcome-blind data rules (config/stage3.yaml `wnba.data_rules`, declared before the first run).

    preseason : dated before the season's first ESPN game (ESPN lists regular season + playoffs only)
    duplicate : SBR lists one game twice (same teams and final score within a day, home/away often
                swapped); a record is kept only if ESPN shows that exact date, home team and score.
    Returns two boolean masks over `lv` (True = drop)."""
    first = box.groupby(box.date.dt.year).date.min()
    preseason = lv.date < (lv.date.dt.year.map(first) - pd.Timedelta(days=1))

    first_name = lv.home <= lv.away
    k = pd.DataFrame({"a": lv.home.where(first_name, lv.away), "b": lv.away.where(first_name, lv.home),
                      "hi": np.maximum(lv.home_pts, lv.away_pts), "lo": np.minimum(lv.home_pts, lv.away_pts),
                      "date": lv.date}, index=lv.index).sort_values(["a", "b", "hi", "lo", "date"])
    gap = k.groupby(["a", "b", "hi", "lo"]).date.diff().dt.days
    cluster = (gap.isna() | (gap > 1)).cumsum()
    size = cluster.map(cluster.value_counts())
    espn = box[box.home_away == "home"][["date", "team_name", "pts", "opp_pts"]]
    seen = set(zip(espn.date, espn.team_name, espn.pts, espn.opp_pts))
    confirmed = pd.Series([(d, h, hp, ap) in seen for d, h, hp, ap in
                           zip(lv.date, lv.home, lv.home_pts, lv.away_pts)], index=lv.index)
    duplicate = (size.reindex(lv.index) > 1) & ~confirmed
    return preseason, duplicate


def match_box_named(g: pd.DataFrame, box: pd.DataFrame) -> pd.DataFrame:
    """ESPN game ids by date (±1 day), the two team names and the score. ESPN and SBR use the same
    franchise names, so two games with the same score on consecutive days (which the shared
    date+score matcher leaves unmatched) stay apart. Adds espn_game_id, espn_home_id, espn_away_id."""
    h = box[box.home_away == "home"][["espn_game_id", "date", "team_name", "team_id", "pts"]]
    a = box[box.home_away == "away"][["espn_game_id", "team_name", "team_id", "pts"]]
    k = h.merge(a, on="espn_game_id", suffixes=("_h", "_a"))

    def key(n1, n2, p1, p2):
        first = n1 <= n2
        return (n1.where(first, n2) + "|" + n2.where(first, n1) + "|"
                + np.maximum(p1, p2).astype(int).astype(str) + "-" + np.minimum(p1, p2).astype(int).astype(str))

    k["key"] = key(k.team_name_h, k.team_name_a, k.pts_h, k.pts_a)
    g = g.copy()
    g["key"] = key(g.home, g.away, g.home_pts, g.away_pts)
    cand = pd.concat([g[["game_key", "date", "key"]].merge(k.assign(date=k.date + pd.Timedelta(days=s)),
                                                           on=["date", "key"]).assign(shift=abs(s))
                      for s in (0, -1, 1)]).sort_values("shift")
    one = cand.groupby("game_key").espn_game_id.transform("nunique") == 1
    cand = cand[one].drop_duplicates("game_key")
    cand = cand[~cand.espn_game_id.duplicated(keep=False)]
    # ESPN team ids by name (the SBR home team may be ESPN's away side at a neutral site)
    cand = cand.merge(g[["game_key", "home"]], on="game_key")
    hm = cand.home == cand.team_name_h
    cand["espn_home_id"] = cand.team_id_h.where(hm, cand.team_id_a)
    cand["espn_away_id"] = cand.team_id_a.where(hm, cand.team_id_h)
    tip = box.drop_duplicates("espn_game_id").set_index("espn_game_id").tip_time
    cand["tip_time"] = cand.espn_game_id.map(tip)
    return g.drop(columns="key").merge(cand[["game_key", "espn_game_id", "tip_time", "espn_home_id", "espn_away_id"]],
                                       on="game_key", how="left")


def unify_wnba(write: bool = True):
    box = load_box(files=fetch_box())
    box = box[box.home_away.isin(["home", "away"])]

    from data import sbr_live
    lv = sbr_live.parse("wnba")
    lv = lv[lv.status.fillna("").str.startswith("Final")].copy()
    lv["home_pts"] = pd.to_numeric(lv.home_pts, errors="coerce")
    lv["away_pts"] = pd.to_numeric(lv.away_pts, errors="coerce")
    lv = lv[lv.home_pts.notna() & lv.away_pts.notna()]
    lv["home_name"], lv["away_name"] = lv.home, lv.away
    lv["home"], lv["away"] = lv.home_name.astype(str).str.strip(), lv.away_name.astype(str).str.strip()
    preseason, duplicate = exhibition_and_duplicates(lv, box)
    dropped = {"preseason": int(preseason.sum()), "duplicate_records": int(duplicate.sum())}
    lv = lv[~preseason & ~duplicate]
    lv["total"] = lv.home_pts + lv.away_pts
    lv["game_key"] = "W" + lv.sbr_game_id.astype(str)
    named = lv.home.ne("None") & lv.away.ne("None") & lv.home.ne("") & lv.away.ne("")
    lv["clean"] = lv.total.between(100, 280) & named
    mv = (lv.line_close - lv.line_open).abs()
    lv["ok_open"] = lv.clean & lv.line_open.between(120, 220) & ~(mv > 20)
    lv["ok_close"] = lv.clean & lv.line_close.between(120, 220) & ~(mv > 20)
    lv["is_real_open"] = 1
    lv["source"] = "sbr_live"

    cols = ["season", "date", "home", "away", "home_name", "away_name", "home_pts", "away_pts", "total",
            "line_open", "line_close", "home_spread_open", "home_spread_close", "ok_open", "ok_close",
            "is_real_open", "books_json", "game_key", "clean", "source"]
    g = lv[cols].reset_index(drop=True)
    g["date"] = pd.to_datetime(g.date)
    g = match_box_named(g, box)
    g["neutral"] = g.season.eq("2020")
    for c in ["away_1h", "home_1h", "away_2h_reg", "home_2h_reg", "line_2h", "home_spread_2h",
              "ml_away", "ml_home", "first_half", "second_half"]:
        g[c] = np.nan
    g["ok_2h"] = False
    g["quality_flags"] = ""
    rep = {"games": len(g), "by_season": g.groupby("season").size().to_dict(),
           "with_open": int(g.ok_open.sum()), "box_matched": float(g.espn_game_id.notna().mean()),
           "teams": int(pd.concat([g.home, g.away]).nunique()), "dropped": dropped}
    if write:
        g.to_parquet(PROC / "wnba_games_unified.parquet", index=False)
        box.to_parquet(PROC / "wnba_box_unified.parquet", index=False)
    return g, box, rep
