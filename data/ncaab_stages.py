"""Season stage of every NCAAB game, from ESPN schedules (sportsdataverse/hoopR mbb_schedule files,
already in data/raw/ncaab). Everything here is known before tip-off (the schedule), except `ot`,
which is an outcome and is used only to describe stages, never as a feature.

  nonconf_home     non-conference game at a campus site (Nov-Dec mostly; "buy games")
  nonconf_neutral  non-conference game at a neutral site (multi-team events, showcases)
  conf_regular     conference regular season
  conf_tournament  conference tournaments (early-mid March)
  ncaa_tournament  the NCAA tournament
  other_postseason NIT, CBI, CIT and the like

Games are joined on ESPN team ids and the date (±1 day), so games without a matched box score
are labelled too.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config_loader import ROOT

SCHED = ROOT / "data" / "raw" / "ncaab"
NCAA_TOURNAMENT_ID = 22
STAGES = ["nonconf_home", "nonconf_neutral", "conf_regular", "conf_tournament", "ncaa_tournament",
          "other_postseason"]
COLS = ["game_id", "date", "season_type", "conference_competition", "neutral_site", "tournament_id",
        "notes_type", "notes_headline", "status_period", "home_id", "away_id", "venue_id", "venue_capacity",
        "venue_indoor", "home_conference_id", "away_conference_id"]


def stage_of(s: pd.DataFrame) -> pd.Series:
    post = s.season_type == 3
    return pd.Series(np.select(
        [post & (s.tournament_id == NCAA_TOURNAMENT_ID), post,
         s.tournament_id.notna(), s.conference_competition.astype(bool),
         s.neutral_site.astype(bool)],
        ["ncaa_tournament", "other_postseason", "conf_tournament", "conf_regular", "nonconf_neutral"],
        "nonconf_home"), index=s.index)


def load_schedules(years=range(2008, 2027)) -> pd.DataFrame:
    import pyarrow.parquet as pq
    frames = []
    for y in years:
        f = SCHED / f"mbb_schedule_{y}.parquet"
        if f.exists():
            have = set(pq.read_schema(f).names)
            frames.append(pd.read_parquet(f, columns=[c for c in COLS if c in have]))   # venue_capacity ends in 2023
    s = pd.concat(frames, ignore_index=True)
    s["date"] = pd.to_datetime(pd.to_datetime(s.date, utc=True).dt.tz_convert("America/New_York").dt.date)
    s["stage"] = stage_of(s)
    s["ot"] = s.status_period > 2
    s["home"] = "e" + s.home_id.astype(str)
    s["away"] = "e" + s.away_id.astype(str)
    return s.drop_duplicates("game_id")


def attach(g: pd.DataFrame, s: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add stage, event name, OT flag and venue fields to games keyed by ESPN team ids (home/away)
    and date. Exact date first, then ±1 day; a pair of teams is matched in either orientation."""
    s = load_schedules() if s is None else s
    keep = ["game_id", "stage", "ot", "notes_headline", "venue_id", "venue_capacity", "venue_indoor",
            "home_conference_id", "away_conference_id"]
    a = s.assign(k1=s.home + "|" + s.away, k2=s.away + "|" + s.home)
    out = []
    left = g[["game_key", "date", "home", "away"]].assign(k=g.home + "|" + g.away)
    for shift in (0, -1, 1):
        for kcol in ("k1", "k2"):
            r = a[["date", kcol] + keep].rename(columns={kcol: "k"})
            r = r.assign(date=r.date + pd.Timedelta(days=shift))
            m = left.merge(r, on=["date", "k"], how="inner").assign(_pri=abs(shift) * 2 + (kcol == "k2"))
            out.append(m)
    m = pd.concat(out).sort_values("_pri").drop_duplicates("game_key")
    m = m[~m.game_id.duplicated(keep="first")]
    return g.merge(m[["game_key"] + keep].rename(columns={"game_id": "sched_game_id"}), on="game_key", how="left")
