"""NBA games in the same schema as the NCAAB pipeline, so the identical feature
builder, models, calibrators and card engines apply.

  2007-08..2020-21 : stage-1 archive (one line per game, treated as both open and close)
  2021-22..2025-26 : sportsbookreview.com — real opening/closing totals, 6 books, prices
  box scores       : ESPN via sportsdataverse/hoopR-nba-data (pinned commit), 2008..2026
"""
from __future__ import annotations

import hashlib
import urllib.request

import numpy as np
import pandas as pd

from config_loader import ROOT
from data.ingest import TEAM_CODES
from data.ncaab_ingest import load_box, match_box

PROC = ROOT / "data" / "processed"
NBA_BOX = ROOT / "data" / "raw" / "nba_box"
HOOPR_NBA_COMMIT = "68b5e92dc21cd7e9d02a4c1e1a812d0ac2034c91"
FIRST_LIVE_SEASON = "2021-22"


def fetch_box(years=range(2008, 2027)) -> list:
    NBA_BOX.mkdir(parents=True, exist_ok=True)
    out = []
    for y in years:
        dest = NBA_BOX / f"team_box_{y}.parquet"
        if not dest.exists():
            url = (f"https://raw.githubusercontent.com/sportsdataverse/hoopR-nba-data/"
                   f"{HOOPR_NBA_COMMIT}/nba/team_box/parquet/team_box_{y}.parquet")
            urllib.request.urlretrieve(url, dest)
        out.append(dest)
    (NBA_BOX / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in out))
    return out


def _code(name: str) -> str:
    return TEAM_CODES.get(str(name).strip(), f"x:{name}")


def unify_nba(write: bool = True):
    box = load_box(files=fetch_box())
    box = box[box.home_away.isin(["home", "away"])]

    # ---------------- archive seasons (single line per game)
    h = pd.read_parquet(PROC / "games.parquet")
    h = h[h.season < FIRST_LIVE_SEASON].copy()
    h["game_key"] = h.game_id
    h["home_name"], h["away_name"] = h.home, h.away
    h["line_open"] = h.line
    h["line_close"] = h.line
    h["home_spread_open"] = h.home_spread
    h["home_spread_close"] = h.home_spread
    ok = h.clean & h.line.between(150, 300)
    h["ok_open"] = ok
    h["ok_close"] = ok
    h["is_real_open"] = 0
    h["books_json"] = np.nan
    h["source"] = "archive"

    # ---------------- live seasons
    from data import sbr_live
    lv = sbr_live.parse("nba")
    lv = lv[lv.status.fillna("").str.startswith("Final")].copy()
    lv["home_pts"] = pd.to_numeric(lv.home_pts, errors="coerce")
    lv["away_pts"] = pd.to_numeric(lv.away_pts, errors="coerce")
    lv = lv[lv.home_pts.notna() & lv.away_pts.notna()]
    lv["home_name"], lv["away_name"] = lv.home, lv.away
    lv["home"] = lv.home_name.map(_code)
    lv["away"] = lv.away_name.map(_code)
    lv["total"] = lv.home_pts + lv.away_pts
    lv["game_key"] = "N" + lv.sbr_game_id.astype(str)
    lv["clean"] = lv.total.between(120, 350) & ~lv.home.str.startswith("x:") & ~lv.away.str.startswith("x:")
    mv = (lv.line_close - lv.line_open).abs()
    lv["ok_open"] = lv.clean & lv.line_open.between(150, 300) & ~(mv > 20)
    lv["ok_close"] = lv.clean & lv.line_close.between(150, 300) & ~(mv > 20)
    lv["is_real_open"] = 1
    lv["is_postseason"] = False
    lv["source"] = "sbr_live"
    lv["quality_flags"] = ""

    cols = ["season", "date", "home", "away", "home_name", "away_name", "home_pts", "away_pts", "total",
            "line_open", "line_close", "home_spread_open", "home_spread_close", "ok_open", "ok_close",
            "is_real_open", "books_json", "game_key", "clean", "source"]
    g = pd.concat([h[cols], lv[cols]], ignore_index=True)
    g["date"] = pd.to_datetime(g.date)
    g = match_box(g, box)
    g["neutral"] = False
    for c in ["away_1h", "home_1h", "away_2h_reg", "home_2h_reg", "line_2h", "home_spread_2h",
              "ml_away", "ml_home", "first_half", "second_half"]:
        g[c] = np.nan
    g["ok_2h"] = False
    g["quality_flags"] = ""
    rep = {"games": len(g), "archive": int((g.source == "archive").sum()),
           "live": int((g.source == "sbr_live").sum()), "box_matched": float(g.espn_game_id.notna().mean()),
           "unknown_teams": int((g.home.str.startswith("x:") | g.away.str.startswith("x:")).sum())}
    if write:
        g.to_parquet(PROC / "nba_games_unified.parquet", index=False)
        box.to_parquet(PROC / "nba_box_unified.parquet", index=False)
    return g, box, rep
