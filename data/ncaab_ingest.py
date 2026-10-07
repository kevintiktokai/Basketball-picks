"""NCAA men's basketball: pinned ingestion of the SBR odds archive (open/close
full-game totals, second-half totals, half scores, moneylines) and ESPN team
box scores (hoopR-mbb-data), joined by date + final score.

Outputs (data/processed/):
  ncaab_games.parquet   one row per game
  ncaab_box.parquet     one row per team-game (ESPN box stats + possessions)

Quality rules use only pre-game information or internal score consistency —
never whether an Over/Under won — so exclusions cannot bias results.
"""
from __future__ import annotations

import hashlib
import re
import urllib.request

import numpy as np
import pandas as pd
import yaml

from config_loader import ROOT

RAW = ROOT / "data" / "raw" / "ncaab"
PROC = ROOT / "data" / "processed"


def stage2_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "stage2.yaml").read_text())


def _sha(p) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def fetch() -> None:
    cfg = stage2_config()["ncaab"]
    RAW.mkdir(parents=True, exist_ok=True)
    jobs = [(f, cfg["sbr_base_url"] + f, h) for f, h in cfg["sbr_files"].items()]
    bs = cfg["box_source"]
    for f, h in cfg["box_files"].items():
        year = re.search(r"(\d{4})", f).group(1)
        url = (f"https://raw.githubusercontent.com/{bs['repo']}/{bs['commit']}/"
               + bs["path_template"].format(year=year))
        jobs.append((f, url, h))
    for name, url, digest in jobs:
        dest = RAW / name
        if not dest.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as out:
                out.write(r.read())
        if _sha(dest) != digest:
            raise RuntimeError(f"checksum mismatch for {name}")


# ----------------------------------------------------------------- SBR parse
def _num(x):
    if isinstance(x, str):
        s = x.strip().lower()
        if s in ("pk", "p"):
            return 0.0
        try:
            return float(s)
        except ValueError:
            return np.nan
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def _split_total_spread(a, b, total_floor):
    """SBR puts the total on one team's row and the spread on the other's.
    Returns (total, spread_on_row_a, spread_on_row_b)."""
    va, vb = _num(a), _num(b)
    tot = np.nan
    sa = sb = np.nan
    cand = [(va, "a"), (vb, "b")]
    big = [(v, k) for v, k in cand if not np.isnan(v) and v >= total_floor]
    small = [(v, k) for v, k in cand if not np.isnan(v) and v < total_floor]
    if len(big) == 1:
        tot = big[0][0]
    if len(small) == 1:
        v, k = small[0]
        if k == "a":
            sa = v
        else:
            sb = v
    return tot, sa, sb


def parse_sbr_season(path, season: str) -> pd.DataFrame:
    d = pd.read_excel(path)
    d = d.reset_index(drop=True)
    start_year = int(season[:4])
    rows = []
    i = 0
    n = len(d)
    while i + 1 < n:
        a, b = d.iloc[i], d.iloc[i + 1]
        if not ((a.VH == "V" and b.VH == "H") or (a.VH == "N" and b.VH == "N")):
            i += 1           # resync on malformed pairs
            continue
        mmdd = int(a.Date)
        month, day = mmdd // 100, mmdd % 100
        year = start_year if month >= 7 else start_year + 1
        try:
            date = pd.Timestamp(year=year, month=month, day=day)
        except ValueError:
            i += 2
            continue
        neutral = a.VH == "N"
        t_open, so_a, so_b = _split_total_spread(a.Open, b.Open, 90)
        t_close, sc_a, sc_b = _split_total_spread(a.Close, b.Close, 90)
        t_2h, s2_a, s2_b = _split_total_spread(a["2H"], b["2H"], 35)
        # home_spread: expected (b - a) margin; b is the home team (or 2nd neutral team)
        def hs(sa, sb):
            if not np.isnan(sb):
                return sb          # b favoured by sb
            if not np.isnan(sa):
                return -sa         # a favoured by sa
            return np.nan
        rows.append({
            "season": season, "date": date, "neutral": neutral,
            "away": str(a.Team).strip(), "home": str(b.Team).strip(),
            "rot_away": a.Rot, "rot_home": b.Rot,
            "away_1h": _num(a["1st"]), "home_1h": _num(b["1st"]),
            "away_2h_reg": _num(a["2nd"]), "home_2h_reg": _num(b["2nd"]),
            "away_pts": _num(a.Final), "home_pts": _num(b.Final),
            "line_open": t_open, "line_close": t_close, "line_2h": t_2h,
            "home_spread_open": hs(so_a, so_b), "home_spread_close": hs(sc_a, sc_b),
            "home_spread_2h": hs(s2_a, s2_b),
            "ml_away": _num(a.ML), "ml_home": _num(b.ML),
        })
        i += 2
    g = pd.DataFrame(rows)
    return g


# ----------------------------------------------------------------- box scores
def load_box(files=None) -> pd.DataFrame:
    """ESPN (hoopR) team box scores -> one row per team-game with possessions.
    `files`: explicit list of parquet paths (any league); default = pinned NCAAB files."""
    if files is None:
        files = [RAW / f for f in stage2_config()["ncaab"]["box_files"]]
    frames = []
    for f in files:
        b = pd.read_parquet(f)
        frames.append(b)
    b = pd.concat(frames, ignore_index=True)
    keep = {
        "game_id": "espn_game_id", "season": "espn_season", "game_date": "date",
        "game_date_time": "tip_time", "team_id": "team_id",
        "team_display_name": "team_name", "team_home_away": "home_away",
        "team_score": "pts", "field_goals_made": "fgm", "field_goals_attempted": "fga",
        "three_point_field_goals_made": "fg3m", "three_point_field_goals_attempted": "fg3a",
        "free_throws_made": "ftm", "free_throws_attempted": "fta",
        "offensive_rebounds": "oreb", "defensive_rebounds": "dreb",
        "total_turnovers": "tov", "turnovers": "tov_alt", "fouls": "pf",
        "opponent_team_id": "opp_id", "opponent_team_score": "opp_pts",
    }
    b = b[[c for c in keep if c in b.columns]].rename(columns=keep)
    b["date"] = pd.to_datetime(b["date"])
    for c in ["pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "tov", "tov_alt",
              "pf", "opp_pts"]:
        if c in b:
            b[c] = pd.to_numeric(b[c], errors="coerce")
    b["tov"] = b["tov"].fillna(b.get("tov_alt"))
    b = b.drop_duplicates(["espn_game_id", "team_id"])
    opp = b[["espn_game_id", "team_id", "fga", "fgm", "fg3a", "fg3m", "fta", "ftm", "oreb", "dreb", "tov"]]
    b = b.merge(opp, left_on=["espn_game_id", "opp_id"], right_on=["espn_game_id", "team_id"],
                suffixes=("", "_opp"), how="left").drop(columns=["team_id_opp"])
    poss_t = b.fga - b.oreb + b.tov + 0.475 * b.fta
    poss_o = b.fga_opp - b.oreb_opp + b.tov_opp + 0.475 * b.fta_opp
    b["poss"] = 0.5 * (poss_t + poss_o)
    b["box_ok"] = (b.poss.between(45, 110) & b.fga.gt(20) & b.fga_opp.gt(20))
    return b


def match_box(g: pd.DataFrame, box: pd.DataFrame) -> pd.DataFrame:
    """Attach ESPN game ids by (date±1, {home_pts, away_pts}) — unique in practice."""
    home_rows = box[["espn_game_id", "date", "team_id", "pts", "opp_id", "opp_pts", "home_away"]]
    key = home_rows.assign(hi=np.maximum(home_rows.pts, home_rows.opp_pts),
                           lo=np.minimum(home_rows.pts, home_rows.opp_pts))
    key = key.sort_values("home_away").drop_duplicates("espn_game_id")   # one row per game
    g = g.copy()
    g["hi"] = np.maximum(g.home_pts, g.away_pts)
    g["lo"] = np.minimum(g.home_pts, g.away_pts)
    out = []
    for shift in (0, -1, 1):
        k = key.assign(date=key.date + pd.Timedelta(days=shift))
        m = g.merge(k[["espn_game_id", "date", "hi", "lo"]], on=["date", "hi", "lo"], how="inner")
        out.append(m[["game_key", "espn_game_id"]].assign(shift=abs(shift)))
    cand = pd.concat(out).sort_values("shift")
    # ambiguous: several ESPN games with same date+scores -> drop the match
    counts = cand.groupby("game_key").espn_game_id.nunique()
    ok = counts[counts == 1].index
    cand = cand[cand.game_key.isin(ok)].drop_duplicates("game_key")
    # one ESPN game matched to two SBR games -> drop both
    dup = cand.espn_game_id.duplicated(keep=False)
    cand = cand[~dup]
    g = g.merge(cand[["game_key", "espn_game_id"]], on="game_key", how="left")
    # team ids for home / away by score (finals cannot tie)
    tid = box[["espn_game_id", "team_id", "pts", "tip_time"]]
    g = g.merge(tid.rename(columns={"team_id": "espn_home_id", "pts": "home_pts"}),
                on=["espn_game_id", "home_pts"], how="left")
    g = g.merge(tid.drop(columns="tip_time").rename(columns={"team_id": "espn_away_id", "pts": "away_pts"}),
                on=["espn_game_id", "away_pts"], how="left")
    return g.drop(columns=["hi", "lo"])


def build(write: bool = True):
    fetch()
    cfg = stage2_config()["ncaab"]
    frames = [parse_sbr_season(RAW / f, re.search(r"(\d{4}-\d{2})", f).group(1))
              for f in cfg["sbr_files"]]
    g = pd.concat(frames, ignore_index=True)
    g["game_key"] = (g.date.dt.strftime("%Y%m%d") + "_" + g.away.str.replace(" ", "")
                     + "@" + g.home.str.replace(" ", ""))
    g = g.drop_duplicates("game_key", keep=False).reset_index(drop=True)
    g["total"] = g.home_pts + g.away_pts
    g["first_half"] = g.home_1h + g.away_1h
    g["second_half"] = g.total - g.first_half          # includes OT, as 2H bets do

    # ---------------- outcome-blind quality flags
    q = pd.Series("", index=g.index)
    q[~g.total.between(60, 250)] += "bad_score;"
    q[(g.home_1h + g.home_2h_reg > g.home_pts) | (g.away_1h + g.away_2h_reg > g.away_pts)] += "half_score_inconsistent;"
    g["quality_flags"] = q
    g["clean"] = q == ""
    g["ok_close"] = g.clean & g.line_close.between(95, 200)
    g["ok_open"] = g.clean & g.line_open.between(95, 200)
    move = (g.line_close - g.line_open).abs()
    g.loc[move > 20, ["ok_open", "ok_close"]] = False          # implausible move = data error
    g["ok_2h"] = g.clean & g.line_2h.between(40, 110) & g.first_half.between(20, 140) & g.ok_close

    box = load_box()
    g = match_box(g, box)
    report = {
        "games": int(len(g)), "clean": int(g.clean.sum()),
        "with_close": int(g.ok_close.sum()), "with_open": int(g.ok_open.sum()),
        "with_2h": int(g.ok_2h.sum()), "box_matched": int(g.espn_game_id.notna().sum()),
        "by_season": g.groupby("season").agg(
            games=("game_key", "size"), close=("ok_close", "sum"), open=("ok_open", "sum"),
            h2=("ok_2h", "sum"), box=("espn_game_id", lambda s: s.notna().sum())).reset_index()
            .to_dict("records"),
    }
    if write:
        PROC.mkdir(parents=True, exist_ok=True)
        g.to_parquet(PROC / "ncaab_games.parquet", index=False)
        box.to_parquet(PROC / "ncaab_box.parquet", index=False)
    return g, box, report


if __name__ == "__main__":
    import json
    _, _, rep = build()
    print(json.dumps(rep, indent=1, default=str))
