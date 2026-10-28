"""NBA player points props from OddsPapi (free key, counted budget: data/oddspapi.py).

What a probe on 28 Oct 2026 found (14 requests): NBA is tournament 132; /historical-odds holds every
book's full pre-game price timeline for each player-points line, keyed by a numeric player id.
Nothing is stored before about 20 Jan 2026; Pinnacle props appear between 24 Jan and 10 Mar 2026,
DraftKings and FanDuel props between 10 Mar and 4 May 2026, and all three carry this season.

One request = one game (up to three books). Responses are slimmed to pre-game player-points prices
and cached, so nothing is requested twice.

usage: python -m data.nba_props probe                       # 2-3 requests: player names, 1xBet/Betway coverage
       python -m data.nba_props backfill FROM TO [--books pinnacle,1xbet,betway] [--max N]
       python -m data.nba_props parse                       # -> data/processed/nba_props.parquet
       python -m data.nba_props names [BOOK ...]            # 1 request per book: player names from live odds
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from data import oddspapi as op

NBA = 132
BOOKS = "pinnacle,1xbet,betway"            # sharp reference + the two books bet at
PROPS = op.RAW / str(NBA) / "props"
NAMES = op.RAW / str(NBA) / "player_names.json"


def points_markets() -> pd.DataFrame:
    """Player-points markets of the catalogue: market id -> line, and outcome id -> side."""
    rows = []
    for m in json.loads((op.RAW / "markets_11.json").read_text()):
        if m.get("playerProp") and m.get("marketType") == "playertotals-points" and m.get("period") == "result":
            for o in m["outcomes"]:
                rows.append({"market_id": int(m["marketId"]), "outcome_id": int(o["outcomeId"]),
                             "line": float(m["handicap"]), "side": o["outcomeName"].lower()})
    return pd.DataFrame(rows)


def slim(data: dict, keep: set, cutoff: pd.Timestamp) -> dict:
    """Pre-game snapshots of player-points markets only, every player kept."""
    books = {}
    for slug, bd in (data.get("bookmakers") or {}).items():
        mk = {}
        for mid, md in (bd.get("markets") or {}).items():
            if int(mid) not in keep:
                continue
            outs = {}
            for oid, od in (md.get("outcomes") or {}).items():
                pl = {pid: [x for x in snaps if pd.Timestamp(x["createdAt"]) < cutoff]
                      for pid, snaps in (od.get("players") or {}).items() if pid != "0"}
                pl = {k: v for k, v in pl.items() if v}
                if pl:
                    outs[oid] = {"players": pl}
            if outs:
                mk[mid] = {"outcomes": outs}
        if mk:
            books[slug] = {"markets": mk}
    return {"fixtureId": data.get("fixtureId"), "bookmakers": books}


def history(f: dict, books: str = BOOKS) -> dict:
    path = PROPS / f"{f['fixtureId']}__{books.replace(',', '_')}.json"
    if path.exists():
        return json.loads(path.read_text())
    keep = set(points_markets().market_id)
    data = op._get_json("/historical-odds", {"fixtureId": f["fixtureId"], "bookmakers": books}) or {}
    out = {**slim(data, keep, op._cutoff(f)), "_books": books,
           "_fixture": {k: f.get(k) for k in ("fixtureId", "startTime", "participant1Name", "participant2Name",
                                              "statusId")}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def participants() -> object:
    """OddsPapi's participant list for basketball (to turn player ids into names); cached raw."""
    return op._cached(op.RAW / "participants_11.json", lambda: op._get_json("/participants", {"sportId": 11}))


def names(books: list[str] | None = None) -> dict:
    """Player id -> "Last, First" from the live odds feed (/odds-by-tournaments carries playerName,
    the history does not). Each book named costs one request; every saved feed is read."""
    for b in books or []:
        data = op._get_json("/odds-by-tournaments", {"bookmaker": b, "tournamentIds": NBA})
        (op.RAW / str(NBA) / f"odds_by_tournament_{b}.json").write_text(json.dumps(data))
    out = json.loads(NAMES.read_text()) if NAMES.exists() else {}
    for p in sorted((op.RAW / str(NBA)).glob("odds_by_tournament_*.json")):
        for f in json.loads(p.read_text()) or []:
            for bd in (f.get("bookmakerOdds") or {}).values():
                for md in (bd.get("markets") or {}).values():
                    for o in (md.get("outcomes") or {}).values():
                        for pid, x in (o.get("players") or {}).items():
                            if pid != "0" and x.get("playerName"):
                                out[pid] = x["playerName"]
    NAMES.write_text(json.dumps(dict(sorted(out.items())), indent=0))
    return out


def backfill(start: str, end: str, books: str = BOOKS, max_games: int | None = None) -> int:
    """Finished NBA games between two dates, oldest first, within the month's budget."""
    now = pd.Timestamp.now(tz="UTC")
    fx = sorted((f for f in op.fixtures(NBA, start, end) if op._finished(f, now)), key=op._start)
    got = 0
    for f in fx:
        if max_games is not None and got >= max_games:
            break
        if (PROPS / f"{f['fixtureId']}__{books.replace(',', '_')}.json").exists():
            continue
        try:
            history(f, books)
        except op.BudgetExhausted:
            break
        got += 1
    return got


def parse() -> pd.DataFrame:
    """Every cached pre-game price: fixture, start, teams, book, player id, line, side, time, price."""
    pm = points_markets().set_index("outcome_id")
    rows = []
    for p in sorted(PROPS.glob("*.json")):
        d = json.loads(p.read_text())
        f = d.get("_fixture") or {}
        for book, bd in d.get("bookmakers", {}).items():
            for md in bd["markets"].values():
                for oid, od in md["outcomes"].items():
                    if int(oid) not in pm.index:
                        continue
                    line, side = float(pm.at[int(oid), "line"]), pm.at[int(oid), "side"]
                    for pid, snaps in od["players"].items():
                        for s in snaps:
                            rows.append((f.get("fixtureId"), f.get("startTime"), f.get("participant1Name"),
                                         f.get("participant2Name"), book, pid, line, side, s["createdAt"],
                                         s.get("price"), s.get("active", True) is not False))
    T = pd.DataFrame(rows, columns=["fixture_id", "start", "home_name", "away_name", "book", "player_id", "line",
                                    "side", "t", "price", "active"])
    T["t"] = pd.to_datetime(T.t, utc=True)
    T["start"] = pd.to_datetime(T.start, utc=True)
    out = op.PROC / "nba_props.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    T.to_parquet(out, index=False)
    return T


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "probe":
        P = participants()
        print("participants:", type(P).__name__, len(P) if hasattr(P, "__len__") else "")
        recent = [f for f in op.fixtures(NBA, (pd.Timestamp.now() - pd.Timedelta(days=4)).strftime("%Y-%m-%d"),
                                         pd.Timestamp.now().strftime("%Y-%m-%d")) if op._finished(f, pd.Timestamp.now(tz="UTC"))]
        if recent:
            h = history(recent[-1], BOOKS)
            print({b: sum(len(o["players"]) for m in v["markets"].values() for o in m["outcomes"].values())
                   for b, v in h["bookmakers"].items()}, "player-line timelines by book")
        print(f"requests used this month: {op.used()} of {op.budget()}")
    elif cmd == "backfill":
        args = [a for a in sys.argv[2:] if not a.startswith("--")]
        books = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--books=")), BOOKS)
        mx = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--max=")), None)
        print("fetched", backfill(args[0], args[1], books, mx), f"games; requests used: {op.used()} of {op.budget()}")
    elif cmd == "names":
        n = names([a for a in sys.argv[2:]])
        print(len(n), f"named player ids; requests used: {op.used()} of {op.budget()}")
    elif cmd == "parse":
        T = parse()
        print(len(T), "prices,", T.fixture_id.nunique(), "games,", T.player_id.nunique(), "players")
    else:
        print(__doc__)
