"""Polite scraper + parser for sportsbookreview.com historical NCAAB odds
(opening and latest totals/spreads with prices, per sportsbook).

Raw JSON for every date is cached under data/raw/sbr_live/ncaab/<market>/<date>.json
and a manifest with sha256 of every cached file is written, so the exact inputs
of any evaluation can be audited. At most one request per second.

usage: python -m data.sbr_live fetch      # download (resumable)
       python -m data.sbr_live parse      # build data/processed/ncaab_live_games.parquet
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

import numpy as np
import pandas as pd
import yaml

from config_loader import ROOT

RAW = ROOT / "data" / "raw" / "sbr_live" / "ncaab"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124 Safari/537.36")
PATHS = {
    "totals": "betting-odds/ncaa-basketball/totals/full-game.json?league=ncaa-basketball"
              "&oddsType=totals&oddsScope=full-game&date={d}",
    "spread": "betting-odds/ncaa-basketball/pointspread/full-game.json?league=ncaa-basketball"
              "&oddsType=spread&oddsScope=full-game&date={d}",
}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def build_id() -> str:
    html = _get("https://www.sportsbookreview.com/betting-odds/ncaa-basketball/").decode("utf-8", "ignore")
    return re.search(r'"buildId":"([^"]+)"', html).group(1)


def season_dates(season: str, start="11-01", end="04-10"):
    y0 = int(season[:4])
    d = date.fromisoformat(f"{y0}-{start}")
    stop = date.fromisoformat(f"{y0 + 1}-{end}")
    while d <= stop:
        yield d
        d += timedelta(days=1)


def fetch(seasons) -> None:
    bid = build_id()
    for season in seasons:
        for d in season_dates(season):
            for market, tmpl in PATHS.items():
                out = RAW / market / f"{d.isoformat()}.json"
                if out.exists():
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                for attempt in range(4):
                    url = f"https://www.sportsbookreview.com/_next/data/{bid}/" + tmpl.format(d=d.isoformat())
                    try:
                        body = _get(url)
                        json.loads(body)
                        out.write_bytes(body)
                        break
                    except urllib.error.HTTPError as e:
                        if e.code == 404:          # build id rotated
                            bid = build_id()
                        time.sleep(2 ** attempt)
                    except Exception:
                        time.sleep(2 ** attempt)
                time.sleep(1.0)
        print(f"fetched {season}", flush=True)
    manifest = {str(p.relative_to(RAW)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(RAW.rglob("*.json"))}
    (RAW / "MANIFEST.json").write_text(json.dumps(manifest, indent=0))


# ------------------------------------------------------------------ parse
def _rows(path):
    try:
        j = json.loads(path.read_text())
        return j["pageProps"]["oddsTables"][0]["oddsTableModel"]["gameRows"]
    except Exception:
        return []


def _season_of(d: pd.Timestamp) -> str:
    y = d.year if d.month >= 7 else d.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def parse() -> pd.DataFrame:
    recs = {}
    for p in sorted((RAW / "totals").glob("*.json")):
        for r in _rows(p):
            gv = r["gameView"]
            gid = gv["gameId"]
            books = {}
            for o in r["oddsViews"]:
                if not o:
                    continue
                ol, cl = o.get("openingLine") or {}, o.get("currentLine") or {}
                books[o["sportsbook"]] = {
                    "open": ol.get("total"), "open_over": ol.get("overOdds"), "open_under": ol.get("underOdds"),
                    "close": cl.get("total"), "close_over": cl.get("overOdds"), "close_under": cl.get("underOdds")}
            cons = gv.get("consensus") or {}
            recs[gid] = {
                "sbr_game_id": gid, "page_date": p.stem, "start": gv.get("startDate"),
                "status": gv.get("gameStatusText"),
                "home": (gv.get("homeTeam") or {}).get("fullName"), "away": (gv.get("awayTeam") or {}).get("fullName"),
                "home_short": (gv.get("homeTeam") or {}).get("displayName"),
                "away_short": (gv.get("awayTeam") or {}).get("displayName"),
                "home_pts": gv.get("homeTeamScore"), "away_pts": gv.get("awayTeamScore"),
                "venue": gv.get("venueName"), "city": gv.get("city"), "state": gv.get("state"),
                "over_pick_pct": cons.get("overPickPercent"), "books_totals": books,
            }
    for p in sorted((RAW / "spread").glob("*.json")):
        for r in _rows(p):
            gid = r["gameView"]["gameId"]
            if gid not in recs:
                continue
            sp = {}
            for o in r["oddsViews"]:
                if not o:
                    continue
                ol, cl = o.get("openingLine") or {}, o.get("currentLine") or {}
                sp[o["sportsbook"]] = {"open_home_spread": ol.get("homeSpread"),
                                       "close_home_spread": cl.get("homeSpread")}
            recs[gid]["books_spread"] = sp
    rows = []
    for g in recs.values():
        bt = g.pop("books_totals")
        bs = g.pop("books_spread", {})
        opens = [v["open"] for v in bt.values() if v["open"] is not None]
        closes = [v["close"] for v in bt.values() if v["close"] is not None]
        sp_open = [v["open_home_spread"] for v in bs.values() if v["open_home_spread"] is not None]
        sp_close = [v["close_home_spread"] for v in bs.values() if v["close_home_spread"] is not None]
        g["line_open"] = float(np.median(opens)) if opens else np.nan
        g["line_close"] = float(np.median(closes)) if closes else np.nan
        g["n_books_open"] = len(opens)
        # SBR homeSpread is negative when the home team is favoured -> flip to our convention
        g["home_spread_open"] = -float(np.median(sp_open)) if sp_open else np.nan
        g["home_spread_close"] = -float(np.median(sp_close)) if sp_close else np.nan
        g["books_json"] = json.dumps(bt)
        rows.append(g)
    df = pd.DataFrame(rows)
    df["start"] = pd.to_datetime(df.start, utc=True)
    # US-Eastern calendar date of tip-off (pages are keyed by US date)
    df["date"] = pd.to_datetime(df.start.dt.tz_convert("America/New_York").dt.date)
    df["season"] = df.date.map(_season_of)
    df = df.drop_duplicates("sbr_game_id")
    out = ROOT / "data" / "processed" / "ncaab_live_raw.parquet"
    df.to_parquet(out, index=False)
    return df


if __name__ == "__main__":
    cfg = yaml.safe_load((ROOT / "config" / "stage2b.yaml").read_text())
    if sys.argv[1] == "fetch":
        fetch(cfg["test_seasons"])
    else:
        d = parse()
        print(d.groupby("season").agg(games=("sbr_game_id", "size"),
                                      final=("status", lambda s: s.fillna("").str.startswith("Final").sum()),
                                      with_open=("line_open", lambda s: s.notna().sum())))
