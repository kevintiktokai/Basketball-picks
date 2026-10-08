"""NCAAB player box scores (ESPN via sportsdataverse/hoopR-mbb-data, pinned commit), for roster
continuity and early-season priors: who played, minutes and production, game by game.
"""
from __future__ import annotations

import hashlib
import urllib.request

import pandas as pd

from config_loader import ROOT

PLAYER_BOX = ROOT / "data" / "raw" / "ncaab_player"
HOOPR_MBB_COMMIT = "13b41edecaf52edc704ef6966eb5ada0bb4167d5"
COLS = ["game_id", "season", "game_date", "team_id", "athlete_id", "minutes", "points", "starter", "did_not_play"]


def fetch(years=range(2008, 2027)) -> list:
    PLAYER_BOX.mkdir(parents=True, exist_ok=True)
    out = []
    for y in years:
        dest = PLAYER_BOX / f"player_box_{y}.parquet"
        if not dest.exists():
            url = (f"https://raw.githubusercontent.com/sportsdataverse/hoopR-mbb-data/"
                   f"{HOOPR_MBB_COMMIT}/mbb/player_box/parquet/player_box_{y}.parquet")
            tmp = dest.with_suffix(".tmp")
            urllib.request.urlretrieve(url, tmp)
            tmp.replace(dest)
        out.append(dest)
    (PLAYER_BOX / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in out))
    return out


def load(years=range(2008, 2027)) -> pd.DataFrame:
    import pyarrow.parquet as pq
    frames = []
    for p in fetch(years):
        have = set(pq.read_schema(p).names)
        frames.append(pd.read_parquet(p, columns=[c for c in COLS if c in have]))
    b = pd.concat(frames, ignore_index=True)
    b["minutes"] = pd.to_numeric(b.minutes, errors="coerce")
    b["points"] = pd.to_numeric(b.points, errors="coerce")
    b["game_date"] = pd.to_datetime(b.game_date)
    return b
