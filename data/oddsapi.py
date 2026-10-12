"""The Odds API adapter (the-odds-api.com, free Starter plan: 500 credits a month) for live
EuroLeague totals: Pinnacle (the sharp reference) and the soft books the European strategy bets
(1xBet, Betway, Unibet), in one request for every upcoming EuroLeague game.

One call = markets x regions credits: totals in regions eu + uk = 2 credits. EuroCup is not covered
by this source (OddsPapi covers it, data/oddspapi.py, when its monthly budget allows).

The key is read from the THE_ODDS_API_KEY environment variable and never written anywhere: the
snapshot files hold only the response body, and errors are reported without the URL.
Every response is kept in data/raw/oddsapi/snapshots/<UTC time>.json, and the credits left after
each call in data/raw/oddsapi/usage.json.

usage: python -m data.oddsapi fetch     # one snapshot (2 credits)
       python -m data.oddsapi usage     # credits left at the last call
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "oddsapi"
SNAP = RAW / "snapshots"
BASE = "https://api.the-odds-api.com/v4"
SPORT = "basketball_euroleague"
REGIONS = "eu,uk"
RESERVE = 10                      # never spend the last credits of the month
BOOK = {"pinnacle": "pinnacle", "onexbet": "1xbet", "betway": "betway"}


class NoKey(RuntimeError):
    pass


def book_name(key: str) -> str:
    if key.startswith("unibet"):
        return "unibet"
    return BOOK.get(key, key)


def usage() -> dict:
    p = RAW / "usage.json"
    return json.loads(p.read_text()) if p.exists() else {}


def fetch(sport: str = SPORT) -> Path:
    """One snapshot of upcoming totals (2 credits). Returns the saved file."""
    key = os.environ.get("THE_ODDS_API_KEY", "").strip()
    if not key:
        raise NoKey("THE_ODDS_API_KEY is not set in this session's environment")
    u = usage()
    if u.get("remaining") is not None and int(u["remaining"]) <= RESERVE:
        raise RuntimeError(f"only {u['remaining']} credits left this month; keeping the reserve of {RESERVE}")
    q = urllib.parse.urlencode({"apiKey": key, "regions": REGIONS, "markets": "totals", "oddsFormat": "decimal",
                                "dateFormat": "iso"})
    req = urllib.request.Request(f"{BASE}/sports/{sport}/odds?{q}", headers={"User-Agent": "basketball-picks/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body, hdr = r.read(), r.headers
    except urllib.error.HTTPError as e:                       # never echo the URL (it holds the key)
        raise RuntimeError(f"The Odds API answered HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}") from None
    json.loads(body)                                          # never keep a bad body
    t = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%SZ")
    SNAP.mkdir(parents=True, exist_ok=True)
    out = SNAP / f"{sport}_{t}.json"
    out.write_bytes(body)
    (RAW / "usage.json").write_text(json.dumps({"at": t, "remaining": hdr.get("x-requests-remaining"),
                                                "used": hdr.get("x-requests-used"), "last": hdr.get("x-requests-last")}))
    return out


def board(path: Path) -> pd.DataFrame:
    """Snapshot -> one row per (game, book, line, side) price, in the shape of
    features.euro_market.timelines(): fixture_id, start, home_name, away_name, book, line, side, t, price, active."""
    snap_t = pd.to_datetime(path.stem.split("_")[-1], format="%Y%m%dT%H%M%SZ", utc=True)
    rows = []
    for ev in json.loads(path.read_text()):
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                if mk.get("key") != "totals":
                    continue
                for o in mk.get("outcomes", []):
                    side = str(o.get("name", "")).lower()
                    if side not in ("over", "under") or o.get("point") is None:
                        continue
                    rows.append({"fixture_id": ev["id"], "start": pd.to_datetime(ev["commence_time"], utc=True),
                                 "home_name": ev.get("home_team"), "away_name": ev.get("away_team"),
                                 "book": book_name(bk["key"]), "line": float(o["point"]), "side": side,
                                 "t": snap_t, "price": float(o["price"]), "active": True,
                                 "book_update": pd.to_datetime(mk.get("last_update") or bk.get("last_update"), utc=True)})
    cols = ["fixture_id", "start", "home_name", "away_name", "book", "line", "side", "t", "price", "active", "book_update"]
    return pd.DataFrame(rows, columns=cols)


def latest_snapshot(sport: str = SPORT) -> Path | None:
    files = sorted(SNAP.glob(f"{sport}_*.json"))
    return files[-1] if files else None


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "usage"
    if cmd == "fetch":
        p = fetch()
        print(f"saved {p.name}; credits left: {usage().get('remaining')}")
    else:
        print(usage() or "no call made yet")
