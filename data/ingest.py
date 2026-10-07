"""Build the canonical game table (data/processed/games.parquet) and the
team-game box-score table (data/processed/team_box.parquet).

One row per game in `games`:
    game_id, season, date, home, away, line, home_spread, ml_home, ml_away,
    home_pts, away_pts, total, is_postseason, box_game_id, quality_flags

All timestamps are calendar dates (US local). The line is the bookmaker total
stored by the source (closing / last pre-game line; see data/SCHEMA.md).
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from config_loader import ROOT, load_config
from data.sources import fetch_all

PROCESSED = ROOT / "data" / "processed"

# franchise code for every name appearing in either source
TEAM_CODES = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "New Jersey Nets": "BKN", "Charlotte Bobcats": "CHA", "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN", "Detroit Pistons": "DET", "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU", "Indiana Pacers": "IND", "LA Clippers": "LAC",
    "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Hornets": "NOP", "New Orleans Pelicans": "NOP", "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC", "Seattle SuperSonics": "OKC", "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}

# last day of the regular season (incl. 2020 seeding games). Later = postseason
# (play-in + playoffs). Public schedule facts, known before each postseason.
REGULAR_SEASON_END = {
    "2007-08": "2008-04-16", "2008-09": "2009-04-16", "2009-10": "2010-04-14",
    "2010-11": "2011-04-13", "2011-12": "2012-04-26", "2012-13": "2013-04-17",
    "2013-14": "2014-04-16", "2014-15": "2015-04-15", "2015-16": "2016-04-13",
    "2016-17": "2017-04-12", "2017-18": "2018-04-11", "2018-19": "2019-04-10",
    "2019-20": "2020-08-14", "2020-21": "2021-05-16", "2021-22": "2022-04-10",
    "2022-23": "2023-04-09", "2023-24": "2024-04-14", "2024-25": "2025-04-13",
    "2025-26": "2026-04-12",
}


def _odds_tables() -> dict[str, str]:
    t = {f"{y}-{str(y + 1)[2:]}": f"odds_{y}-{str(y + 1)[2:]}_new" for y in range(2007, 2023)}
    t.update({"2023-24": "2023-24", "2024-25": "2024-25", "2025-26": "odds_2025-26"})
    return t


def load_odds(path) -> pd.DataFrame:
    con = sqlite3.connect(path)
    frames = []
    for season, table in _odds_tables().items():
        d = pd.read_sql(f'SELECT * FROM "{table}"', con)
        d["season"] = season
        d["source_table"] = table
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["Date"].astype(str).str[:10], format="%Y-%m-%d")
    df["home"] = df["Home"].map(TEAM_CODES)
    df["away"] = df["Away"].map(TEAM_CODES)
    if df[["home", "away"]].isna().any().any():
        bad = set(df.loc[df.home.isna(), "Home"]) | set(df.loc[df.away.isna(), "Away"])
        raise ValueError(f"unmapped team names: {bad}")
    return df


def load_box(reg_path, po_path) -> pd.DataFrame:
    reg = pd.read_csv(reg_path)
    po = pd.read_csv(po_path)
    box = pd.concat([reg, po], ignore_index=True)
    box["date"] = pd.to_datetime(box["GAME_DATE"].str[:10])
    box["team"] = box["TEAM_NAME"].map(TEAM_CODES)
    box["is_home"] = box["MATCHUP"].str.contains(" vs. ")
    box = box.drop_duplicates(["GAME_ID", "TEAM_ID"])
    keep = ["GAME_ID", "SEASON_YEAR", "date", "team", "is_home", "MIN", "PTS", "FGM",
            "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "TOV", "STL", "BLK", "PF"]
    box = box[keep].rename(columns={"GAME_ID": "box_game_id", "SEASON_YEAR": "season"})
    # attach opponent line so each row has both sides
    opp = box[["box_game_id", "team", "PTS", "FGA", "FG3A", "FTA", "OREB", "DREB", "TOV", "FGM", "FG3M"]]
    box = box.merge(opp, on="box_game_id", suffixes=("", "_opp"))
    box = box[box.team != box.team_opp].copy()
    box = box.rename(columns={"team_opp": "opp"})
    # possessions (standard estimate, averaged over both teams)
    poss_t = box.FGA - box.OREB + box.TOV + 0.44 * box.FTA
    poss_o = box.FGA_opp - box.OREB_opp + box.TOV_opp + 0.44 * box.FTA_opp
    box["poss"] = 0.5 * (poss_t + poss_o)
    box["minutes"] = box["MIN"].clip(lower=48)
    return box.reset_index(drop=True)


def build(write: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    paths = fetch_all()
    odds = load_odds(paths["odds"])
    box = load_box(paths["box_regular"], paths["box_playoffs"])
    report: dict = {}

    g = odds.copy()
    g["total"] = g["Points"].astype(float)
    # Win_Margin is home minus away (validated against box scores below)
    g["home_pts"] = (g["total"] + g["Win_Margin"]) / 2
    g["away_pts"] = (g["total"] - g["Win_Margin"]) / 2
    g["line"] = g["OU"].astype(float)
    g["ml_home"] = pd.to_numeric(g["ML_Home"], errors="coerce")
    g["ml_away"] = pd.to_numeric(g["ML_Away"], errors="coerce")
    g["spread_raw"] = pd.to_numeric(
        g["Spread"].replace({"PK": 0, "pk": 0, "PK ": 0}), errors="coerce")
    g["is_postseason"] = g.apply(
        lambda r: r["date"] > pd.Timestamp(REGULAR_SEASON_END[r["season"]]), axis=1
    )

    # ---------- join to box scores (home team perspective) ----------
    home_box = box[box.is_home][["box_game_id", "date", "team", "opp", "PTS", "PTS_opp"]]
    home_box = home_box.rename(columns={"team": "home", "opp": "away", "PTS": "box_home_pts",
                                        "PTS_opp": "box_away_pts"})
    g = g.merge(home_box, on=["date", "home", "away"], how="left")
    # some sources stamp late games on the next UTC day: try date-1 for unmatched
    miss = g.box_game_id.isna()
    if miss.any():
        alt = home_box.copy()
        alt["date"] = alt["date"] + pd.Timedelta(days=1)
        fill = g.loc[miss, ["date", "home", "away"]].reset_index().merge(
            alt, on=["date", "home", "away"], how="inner").set_index("index")
        for c in ["box_game_id", "box_home_pts", "box_away_pts"]:
            g.loc[fill.index, c] = fill[c]
        report["box_matched_on_shifted_date"] = int(len(fill))

    # ---------- quality flags ----------
    g = g.sort_values(["date", "home"]).reset_index(drop=True)
    g["quality_flags"] = ""
    g.loc[g.total <= 0, "quality_flags"] += "no_result;"
    has_box = g.box_game_id.notna()
    box_total = g.box_home_pts + g.box_away_pts
    g.loc[has_box & (box_total != g.total), "quality_flags"] += "score_mismatch_vs_box;"
    # line plausibility. Rules use only pre-game information (never the result),
    # so they cannot bias the sample toward wins/losses:
    #  - NBA full-game totals outside [150, 300] are data-entry errors
    #  - an identical (line, spread) pair on >=3 games of one date is a placeholder
    bad_range = (g.line < 150) | (g.line > 300)
    placeholder = g.groupby(["date", "line", "spread_raw"])["line"].transform("size") >= 3
    g.loc[bad_range, "quality_flags"] += "implausible_line;"
    g.loc[placeholder & ~bad_range, "quality_flags"] += "placeholder_line;"
    g.loc[g.duplicated(["date", "home", "away"], keep=False), "quality_flags"] += "duplicate;"

    # spread sign: make home_spread = expected home margin (positive => home favoured)
    sign = {}
    for s, d in g.groupby("season"):
        ok = d.ml_home.notna() & d.ml_away.notna() & d.spread_raw.notna()
        fav = np.where(d.ml_home[ok] < d.ml_away[ok], 1.0, -1.0)
        c = np.corrcoef(fav, d.spread_raw[ok])[0, 1]
        sign[s] = 1.0 if c > 0 else -1.0
    g["home_spread"] = g.spread_raw * g.season.map(sign)
    bad_spread = g.home_spread.abs() > 30
    g.loc[bad_spread, "home_spread"] = np.nan  # spread is a feature only; keep the game
    report["spread_set_missing"] = int(bad_spread.sum())
    report["spread_sign_by_season"] = sign

    g["game_id"] = (g.date.dt.strftime("%Y%m%d") + "_" + g.away + "@" + g.home)
    g["clean"] = g.quality_flags == ""

    # ---------- report ----------
    seasons_with_box = sorted(box.season.unique())
    rep = []
    for s, d in g.groupby("season"):
        rep.append({
            "season": s, "games": len(d), "postseason": int(d.is_postseason.sum()),
            "clean": int(d.clean.sum()),
            "no_result": int(d.quality_flags.str.contains("no_result").sum()),
            "implausible_line": int(d.quality_flags.str.contains("implausible_line").sum()),
            "placeholder_line": int(d.quality_flags.str.contains("placeholder_line").sum()),
            "score_mismatch": int(d.quality_flags.str.contains("score_mismatch").sum()),
            "box_matched": int(d.box_game_id.notna().sum()) if s in seasons_with_box else None,
        })
    report["by_season"] = rep

    games = g[["game_id", "season", "date", "home", "away", "line", "home_spread", "ml_home",
               "ml_away", "home_pts", "away_pts", "total", "is_postseason", "box_game_id",
               "quality_flags", "clean"]].copy()
    if write:
        PROCESSED.mkdir(parents=True, exist_ok=True)
        games.to_parquet(PROCESSED / "games.parquet", index=False)
        box.to_parquet(PROCESSED / "team_box.parquet", index=False)
    return games, box, report


if __name__ == "__main__":
    import json
    _, _, rep = build()
    print(json.dumps(rep, indent=1, default=str))
