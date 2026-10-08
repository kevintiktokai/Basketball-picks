"""Roster continuity of NCAAB teams, point in time, from ESPN player box scores (data/ncaab_players.py).

For team T in season S and a game on date D, using only T's games before D:
  cont : share of T's minutes last season (S-1) played by players who have already appeared
         (minutes > 0) for T this season
  xfer : minutes those already-seen players played for OTHER teams last season (incoming
         transfers), as a share of T's own minutes last season
Before a team's first game of the season both are unknown (NaN). The first season in the data has
no previous season, so it is NaN throughout.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def player_seasons(pb: pd.DataFrame) -> pd.DataFrame:
    """Minutes per (season, team, player), for players who actually played."""
    p = pb[(pb.minutes > 0) & pb.athlete_id.notna() & pb.team_id.notna()]
    return p.groupby(["season", "team_id", "athlete_id"], as_index=False).minutes.sum()


def continuity(pb: pd.DataFrame) -> pd.DataFrame:
    """One row per (season, team_id, date) on which the team played: cont and xfer before that date."""
    p = pb[(pb.minutes > 0) & pb.athlete_id.notna() & pb.team_id.notna()].copy()
    ps = player_seasons(pb)
    prev = ps.assign(season=ps.season + 1)                                    # last season, keyed by this season
    team_prev_total = prev.groupby(["season", "team_id"]).minutes.sum()
    own_prev = prev.set_index(["season", "team_id", "athlete_id"]).minutes
    # each player's minutes last season for teams other than the one he plays for now
    any_prev = prev.groupby(["season", "athlete_id"]).minutes.sum()
    first = p.groupby(["season", "team_id", "athlete_id"]).game_date.min().reset_index(name="first")
    first["own"] = own_prev.reindex(pd.MultiIndex.from_frame(first[["season", "team_id", "athlete_id"]])).fillna(0).values
    first["other"] = (any_prev.reindex(pd.MultiIndex.from_frame(first[["season", "athlete_id"]])).fillna(0).values
                      - first.own)
    games = p.groupby(["season", "team_id"]).game_date.unique()
    rows = []
    for (s, t), g in first.groupby(["season", "team_id"]):
        tot = team_prev_total.get((s, t), np.nan)
        g = g.sort_values("first")
        f = g["first"].values
        cum_own, cum_other = np.cumsum(g.own.values), np.cumsum(g.other.values)
        for D in np.sort(games.get((s, t), np.array([], dtype="datetime64[ns]"))):
            k = np.searchsorted(f, D, "left")                               # players first seen before D
            if k == 0 or not np.isfinite(tot) or tot <= 0:
                cont = xfer = np.nan
            else:
                cont, xfer = cum_own[k - 1] / tot, cum_other[k - 1] / tot
            rows.append((s, t, D, cont, xfer))
    return pd.DataFrame(rows, columns=["season", "team_id", "date", "cont", "xfer"])


def attach(g: pd.DataFrame, cont: pd.DataFrame) -> pd.DataFrame:
    """Add home_cont, away_cont, home_xfer, away_xfer to games with ESPN team ids (espn_home_id /
    espn_away_id) and dates; joined on the team's game date (±1 day for time-zone edges)."""
    c = cont.copy()
    c["team_id"] = c.team_id.astype("int64")
    c["date"] = pd.to_datetime(c.date).dt.normalize()
    out = g.copy()
    for side in ("home", "away"):
        tid = pd.to_numeric(out[f"espn_{side}_id"], errors="coerce")
        if tid.isna().all():
            tid = pd.to_numeric(out[side].astype(str).str.lstrip("e"), errors="coerce")
        key = pd.DataFrame({"team_id": tid, "date": pd.to_datetime(out.date).dt.normalize()}, index=out.index)
        vals = pd.DataFrame(index=out.index, columns=["cont", "xfer"], dtype=float)
        for shift in (0, -1, 1):
            k = key.assign(date=key.date + pd.Timedelta(days=shift)).dropna()
            k["team_id"] = k.team_id.astype("int64")
            m = k.reset_index().merge(c[["team_id", "date", "cont", "xfer"]], on=["team_id", "date"], how="inner")
            m = m.drop_duplicates("index").set_index("index")
            todo = vals.cont.isna() & vals.index.isin(m.index)
            vals.loc[todo, ["cont", "xfer"]] = m.loc[todo[todo].index, ["cont", "xfer"]].values
        out[f"{side}_cont"], out[f"{side}_xfer"] = vals.cont.values, vals.xfer.values
    return out
