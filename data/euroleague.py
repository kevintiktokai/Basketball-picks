"""EuroLeague / EuroCup adapter (official API, free): games, team box scores, referees.

Polite, cached fetcher: one results call per season + one Boxscore call per game; raw
JSON/XML is stored under data/raw/euroleague/<seasoncode>/ and never re-downloaded.

  seasoncode: E<year> = EuroLeague season starting <year>, U<year> = EuroCup.
  Outputs data/processed/euro_games.parquet (one row per game, with the three referees and
  attendance) and euro_box.parquet (one row per team-game, with possessions).

usage: python -m data.euroleague                 # EuroLeague + EuroCup 2016-17..2025-26
       python -m data.euroleague E2026 U2026     # specific seasons (re-run to pick up new games)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from config_loader import ROOT

RAW = ROOT / "data" / "raw" / "euroleague"
PROC = ROOT / "data" / "processed"
UA = {"User-Agent": "Mozilla/5.0 (research; polite)"}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


STATS_MAP = {"Points": "points", "FieldGoalsMade2": "fieldGoalsMade2", "FieldGoalsAttempted2": "fieldGoalsAttempted2",
             "FieldGoalsMade3": "fieldGoalsMade3", "FieldGoalsAttempted3": "fieldGoalsAttempted3",
             "FreeThrowsMade": "freeThrowsMade", "FreeThrowsAttempted": "freeThrowsAttempted",
             "OffensiveRebounds": "offensiveRebounds", "DefensiveRebounds": "defensiveRebounds",
             "Turnovers": "turnovers", "FoulsCommited": "foulsCommited"}


def _game_v3(code: str, gc: str) -> bytes:
    """Team totals, referees and attendance from the newer API (~3x faster than the legacy
    Boxscore call, identical numbers), stored in the legacy layout so parse() is unchanged."""
    base = f"https://api-live.euroleague.net/v2/competitions/{code[0]}/seasons/{code}/games/{gc}"
    g = json.loads(_get(base))
    s = json.loads(_get(base.replace("/v2/", "/v3/") + "/stats"))
    refs = ", ".join(g[f"referee{i}"]["name"] for i in (1, 2, 3, 4) if g.get(f"referee{i}"))
    stats = [{"Team": g[side]["club"]["name"], "totr": {k: s[side]["total"][v] for k, v in STATS_MAP.items()}}
             for side in ("local", "road")]
    return json.dumps({"_source": "v2+v3", "Referees": refs, "Attendance": g.get("audience"),
                       "Stats": stats}).encode()


def fetch_game(code: str, gc: str, delay: float = 0.3) -> bool:
    """One game, cached; newer API first, legacy Boxscore as fallback; atomic write."""
    out = RAW / code / f"box_{gc}.json"
    if out.exists():
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        try:
            body = _game_v3(code, gc) if attempt < 2 else \
                _get(f"https://live.euroleague.net/api/Boxscore?gamecode={gc}&seasoncode={code}")
            json.loads(body)
            tmp = out.with_suffix(".tmp")
            tmp.write_bytes(body)
            tmp.replace(out)
            time.sleep(delay)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(2 ** attempt)
    return False


def _is_current(code: str) -> bool:
    return pd.Timestamp.now() < pd.Timestamp(f"{int(code[1:]) + 1}-07-01")


def season_games(code: str, max_age_hours: float = 6.0) -> list[str]:
    """Codes of a season's played games. A finished season's list is cached for good; the
    current season's list is re-downloaded when older than `max_age_hours`."""
    d = RAW / code
    d.mkdir(parents=True, exist_ok=True)
    res = d / "results.xml"
    stale = res.exists() and _is_current(code) and time.time() - res.stat().st_mtime > max_age_hours * 3600
    if not res.exists() or stale:
        body = _get(f"https://api-live.euroleague.net/v1/results?seasonCode={code}")
        ET.fromstring(body)                                   # never replace a good file with a bad one
        res.write_bytes(body)
    return [g.findtext("gamecode", "").split("_")[-1] for g in ET.fromstring(res.read_bytes()).iter("game")
            if g.findtext("played", "true") == "true"]


def fetch_season(code: str, workers: int = 4) -> int:
    """All games of a season; a few parallel requests (the API answers in ~1 s each)."""
    todo = [gc for gc in season_games(code) if not (RAW / code / f"box_{gc}.json").exists()]
    with ThreadPoolExecutor(workers) as ex:
        return sum(ex.map(lambda gc: fetch_game(code, gc), todo))


def _refs(s: str) -> list[str]:
    """'JAVOR, DAMIR, PEERANDI, RAIN, SUKYS, ARTURAS' -> ['JAVOR, DAMIR', 'PEERANDI, RAIN', ...]"""
    parts = [p.strip() for p in str(s or "").split(",") if p.strip()]
    return [f"{parts[i]}, {parts[i + 1]}" for i in range(0, len(parts) - 1, 2)]


def parse(codes) -> tuple[pd.DataFrame, pd.DataFrame]:
    games, box = [], []
    for code in codes:
        d = RAW / code
        if not (d / "results.xml").exists():
            continue
        comp = "euroleague" if code.startswith("E") else "eurocup"
        y = int(code[1:])
        season = f"{y}-{str(y + 1)[2:]}"
        root = ET.fromstring((d / "results.xml").read_bytes())
        for g in root.iter("game"):
            if g.findtext("played", "true") != "true":
                continue
            gc = g.findtext("gamecode", "").split("_")[-1]
            f = d / f"box_{gc}.json"
            if not f.exists():
                continue
            b = json.loads(f.read_text())
            try:
                date = pd.to_datetime(g.findtext("date"), format="%b %d, %Y")
            except Exception:  # noqa: BLE001
                continue
            home, away = g.findtext("homecode"), g.findtext("awaycode")
            hs, as_ = pd.to_numeric(g.findtext("homescore"), errors="coerce"), pd.to_numeric(g.findtext("awayscore"), errors="coerce")
            refs = _refs(b.get("Referees"))
            key = f"{code}_{gc}"
            games.append({"game_key": key, "competition": comp, "season": season, "date": date,
                          "round": g.findtext("round"), "home": home, "away": away,
                          "home_name": g.findtext("hometeam"), "away_name": g.findtext("awayteam"),
                          "home_pts": hs, "away_pts": as_, "total": hs + as_,
                          "ref1": refs[0] if len(refs) > 0 else None, "ref2": refs[1] if len(refs) > 1 else None,
                          "ref3": refs[2] if len(refs) > 2 else None,
                          "attendance": pd.to_numeric(b.get("Attendance"), errors="coerce")})
            stats = b.get("Stats") or []
            if len(stats) != 2:
                continue
            rows = []
            for s, team in zip(stats, (home, away)):
                t = s.get("totr") or {}
                rows.append({"game_key": key, "team": team, "pts": t.get("Points"),
                             "fg2m": t.get("FieldGoalsMade2"), "fg2a": t.get("FieldGoalsAttempted2"),
                             "fg3m": t.get("FieldGoalsMade3"), "fg3a": t.get("FieldGoalsAttempted3"),
                             "ftm": t.get("FreeThrowsMade"), "fta": t.get("FreeThrowsAttempted"),
                             "oreb": t.get("OffensiveRebounds"), "dreb": t.get("DefensiveRebounds"),
                             "tov": t.get("Turnovers"), "pf": t.get("FoulsCommited")})
            rows[0]["opp_idx"], rows[1]["opp_idx"] = 1, 0
            for i, r in enumerate(rows):
                o = rows[1 - i]
                r.update({f"{k}_opp": o[k] for k in ("pts", "fg2a", "fg3a", "fta", "oreb", "dreb", "tov", "pf")})
                box.append(r)
    G = pd.DataFrame(games)
    B = pd.DataFrame(box)
    if G.empty or B.empty:
        return G, B
    for c in B.columns:
        if c not in ("game_key", "team"):
            B[c] = pd.to_numeric(B[c], errors="coerce")
    fga = B.fg2a + B.fg3a
    fga_o = B.fg2a_opp + B.fg3a_opp
    B["poss"] = 0.5 * ((fga - B.oreb + B.tov + 0.44 * B.fta) + (fga_o - B.oreb_opp + B.tov_opp + 0.44 * B.fta_opp))
    G = G[G.home_pts.notna() & G.away_pts.notna() & (G.total > 80)]
    return G.reset_index(drop=True), B


if __name__ == "__main__":
    codes = sys.argv[1:] or [f"{c}{y}" for c in ("E", "U") for y in range(2016, 2026)]
    for c in codes:
        n = fetch_season(c)
        print(f"{c}: fetched {n} new box scores", flush=True)
    G, B = parse(codes)
    G.to_parquet(PROC / "euro_games.parquet", index=False)
    B.to_parquet(PROC / "euro_box.parquet", index=False)
    print(G.groupby(["competition", "season"]).size().to_string())
