"""Unify NCAAB archive seasons (SBR archive, 2007-08..2020-21) and live-site seasons
(sportsbookreview.com, 2021-22..2025-26) under ESPN team ids, so ratings and team
histories carry across the boundary.

Outputs data/processed/ncaab_games_unified.parquet and ncaab_box_unified.parquet.
"""
from __future__ import annotations

import glob

import numpy as np
import pandas as pd

from config_loader import ROOT
from data.ncaab_ingest import RAW, load_box, match_box

PROC = ROOT / "data" / "processed"


def load_all_box() -> pd.DataFrame:
    """ESPN team box scores for every NCAAB season present in data/raw/ncaab (2008..2026)."""
    files = sorted(glob.glob(str(RAW / "team_box_*.parquet")))
    return load_box(files=files)


def load_schedules() -> pd.DataFrame:
    frames = []
    for p in sorted(glob.glob(str(RAW / "mbb_schedule_*.parquet"))):
        s = pd.read_parquet(p, columns=["game_id", "neutral_site"])
        frames.append(s)
    s = pd.concat(frames, ignore_index=True).drop_duplicates("game_id")
    s["game_id"] = pd.to_numeric(s.game_id, errors="coerce")
    return s.rename(columns={"game_id": "espn_game_id"})


def _name_to_id(df: pd.DataFrame, name_col: str, id_col: str) -> dict:
    m = df[[name_col, id_col]].dropna()
    if m.empty:
        return {}
    top = m.groupby([name_col, id_col]).size().reset_index(name="n")
    top = top.sort_values("n", ascending=False).drop_duplicates(name_col)
    return dict(zip(top[name_col], top[id_col].astype(int)))


def unify(write: bool = True, include_live: bool = True):
    arch = pd.read_parquet(PROC / "ncaab_games.parquet")
    box = load_all_box()
    sched = load_schedules()

    # ---------------- archive: name -> ESPN id (majority over matched games)
    m_home = _name_to_id(arch, "home", "espn_home_id")
    m_away = _name_to_id(arch, "away", "espn_away_id")
    amap = {**m_away, **m_home}
    arch["home_name"], arch["away_name"] = arch.home, arch.away
    arch["home"] = arch.home_name.map(lambda n: f"e{amap[n]}" if n in amap else f"sbr:{n}")
    arch["away"] = arch.away_name.map(lambda n: f"e{amap[n]}" if n in amap else f"sbr:{n}")
    arch["source"] = "sbr_archive"

    cols = ["season", "date", "neutral", "away", "home", "away_name", "home_name", "away_1h", "home_1h",
            "away_2h_reg", "home_2h_reg", "away_pts", "home_pts", "line_open", "line_close", "line_2h",
            "home_spread_open", "home_spread_close", "home_spread_2h", "ml_away", "ml_home",
            "game_key", "total", "first_half", "second_half", "quality_flags", "clean", "ok_close",
            "ok_open", "ok_2h", "espn_game_id", "espn_home_id", "espn_away_id", "tip_time", "source"]
    if not include_live:
        u = arch[cols].copy()
        if write:
            u.to_parquet(PROC / "ncaab_games_unified.parquet", index=False)
            box.to_parquet(PROC / "ncaab_box_unified.parquet", index=False)
        return u, box, {"archive_games": len(u),
                        "archive_team_keys_espn_share": float(arch.home.str.startswith("e").mean())}

    # ---------------- live site seasons
    live = pd.read_parquet(PROC / "ncaab_live_raw.parquet")
    live = live[live.status.fillna("").str.startswith("Final")].copy()
    live["home_pts"] = pd.to_numeric(live.home_pts, errors="coerce")
    live["away_pts"] = pd.to_numeric(live.away_pts, errors="coerce")
    live = live[live.home_pts.notna() & live.away_pts.notna()]
    live["home_name"], live["away_name"] = live.home, live.away
    live["game_key"] = "L" + live.sbr_game_id.astype(str)
    live = match_box(live.rename(columns={}), box)
    lm_home = _name_to_id(live, "home_name", "espn_home_id")
    lm_away = _name_to_id(live, "away_name", "espn_away_id")
    lmap = {**lm_away, **lm_home}
    live["home"] = live.home_name.map(lambda n: f"e{lmap[n]}" if n in lmap else f"sbrlive:{n}")
    live["away"] = live.away_name.map(lambda n: f"e{lmap[n]}" if n in lmap else f"sbrlive:{n}")
    live = live.merge(sched, on="espn_game_id", how="left")
    live["neutral"] = live.neutral_site.fillna(False).astype(bool)
    live["total"] = live.home_pts + live.away_pts
    for c in ["away_1h", "home_1h", "away_2h_reg", "home_2h_reg", "line_2h", "home_spread_2h",
              "ml_away", "ml_home", "rot_away", "rot_home"]:
        live[c] = np.nan
    live["first_half"] = np.nan
    live["second_half"] = np.nan
    live["quality_flags"] = ""
    live.loc[~live.total.between(60, 250), "quality_flags"] += "bad_score;"
    live["clean"] = live.quality_flags == ""
    live["ok_close"] = live.clean & live.line_close.between(95, 200)
    live["ok_open"] = live.clean & live.line_open.between(95, 200)
    mv = (live.line_close - live.line_open).abs()
    live.loc[mv > 20, ["ok_open", "ok_close"]] = False
    live["ok_2h"] = False
    live["source"] = "sbr_live"

    extra_live = ["n_books_open", "books_json", "over_pick_pct", "sbr_game_id"]
    u = pd.concat([arch[cols], live[cols + extra_live]], ignore_index=True)
    # two odds sources must never overlap in time
    assert u[u.source == "sbr_live"].date.min() > u[u.source == "sbr_archive"].date.max()
    rep = {
        "archive_games": int((u.source == "sbr_archive").sum()),
        "archive_team_keys_espn_share": float(arch.home.str.startswith("e").mean()),
        "live_games": int((u.source == "sbr_live").sum()),
        "live_box_matched": float(live.espn_game_id.notna().mean()),
        "live_team_keys_espn_share": float(live.home.str.startswith("e").mean()),
        "live_by_season": live.groupby("season").agg(games=("game_key", "size"),
                                                     open=("ok_open", "sum"),
                                                     close=("ok_close", "sum")).reset_index().to_dict("records"),
    }
    if write:
        u.to_parquet(PROC / "ncaab_games_unified.parquet", index=False)
        box.to_parquet(PROC / "ncaab_box_unified.parquet", index=False)
    return u, box, rep


if __name__ == "__main__":
    import json
    _, _, rep = unify()
    print(json.dumps(rep, indent=1, default=str))
