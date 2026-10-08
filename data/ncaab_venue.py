"""Venue features for NCAAB totals, point in time (study 6, config/improvements.yaml `study_6`).

venue_factor   the home floor's "park factor": the home team's earlier non-neutral home games, from
               the first day of the season three seasons back up to the day before the game,
               shrunk mean of (final total - closing total) = sum / (n + 40). Neutral sites: 0.
high_altitude  the venue's city (ESPN schedule) is one of 17 college towns at roughly 4,200 ft or
               higher; unknown venue: 0.
Both use only what is known before tip-off: earlier games' finals and closing totals, and the venue.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

K, SEASONS_BACK = 40, 3
HIGH_ALT = {"laramie", "fort collins", "colorado springs", "albuquerque", "logan", "provo", "salt lake city", "ogden",
            "orem", "cedar city", "boulder", "denver", "greeley", "bozeman", "reno", "flagstaff", "pocatello"}


def venue_factor(hist: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
    """hist: games with season, date, home, neutral, total, line_close, ok_close, clean.
    target: games with season, date, home and a neutral flag (`neutral` or `neutral_i`)."""
    H = hist[~hist.neutral.astype(bool) & hist.ok_close.astype(bool) & hist.clean.astype(bool)
             & hist.line_close.notna() & hist.total.notna()]
    H = H.assign(e=H.total - H.line_close).sort_values("date")
    starts = pd.concat([hist[["season", "date"]], target[["season", "date"]]]).groupby("season").date.min().sort_index()
    seasons = list(starts.index)
    win_start = {s: np.datetime64(starts[seasons[max(0, i - SEASONS_BACK)]]) for i, s in enumerate(seasons)}
    by_team = {t: (g.date.values, np.concatenate([[0.0], np.cumsum(g.e.values)])) for t, g in H.groupby("home")}
    neutral = (target.neutral if "neutral" in target else target.neutral_i).astype(bool).values
    out = np.zeros(len(target))
    for i, (t, d, s) in enumerate(zip(target.home.values, target.date.values, target.season.values)):
        h = by_team.get(t)
        if neutral[i] or h is None:
            continue
        a, b = np.searchsorted(h[0], win_start[s], "left"), np.searchsorted(h[0], d, "left")
        out[i] = (h[1][b] - h[1][a]) / (b - a + K)
    return out


def high_altitude(target: pd.DataFrame, sched: pd.DataFrame | None = None) -> np.ndarray:
    """1 if the game's ESPN venue city is in HIGH_ALT, else 0 (also when the venue is unknown)."""
    if sched is None:
        sched = schedule_cities()
    city = target.espn_game_id.map(sched.set_index("game_id").city)
    return city.isin(HIGH_ALT).astype(float).values


def schedule_cities() -> pd.DataFrame:
    import glob

    import pyarrow.parquet as pq

    from config_loader import ROOT
    frames = []
    for f in sorted(glob.glob(str(ROOT / "data" / "raw" / "ncaab" / "mbb_schedule_*.parquet"))):
        have = set(pq.read_schema(f).names)
        frames.append(pd.read_parquet(f, columns=[c for c in ("game_id", "venue_address_city") if c in have]))
    s = pd.concat(frames, ignore_index=True).drop_duplicates("game_id")
    s["city"] = s.venue_address_city.fillna("").str.strip().str.lower()
    return s[["game_id", "city"]]
