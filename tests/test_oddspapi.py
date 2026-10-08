"""Offline tests for the OddsPapi free-tier (v4) adapter, against responses shaped like the
documented API: /markets, /fixtures and /historical-odds."""
import io
import json
import urllib.parse

import pandas as pd
import pytest

import data.oddspapi as op


def _mk(mid, name, lo, hi, *, mtype="totals", period="result", line=None, prop=False, sides=("Over", "Under")):
    m = {"marketId": mid, "marketName": name, "outcomes": [{"outcomeId": lo, "outcomeName": sides[0]},
                                                          {"outcomeId": hi, "outcomeName": sides[1]}]}
    if mtype is not None:
        m.update({"marketType": mtype, "period": period, "handicap": line, "playerProp": prop})
    return m


MARKETS = [
    _mk(1100, "Over Under (incl. overtime)", 1101, 1102, line=158.5),
    _mk(1110, "Over Under (incl. overtime)", 1111, 1112, line=160.5),
    _mk(1120, "Over Under (incl. overtime)", 1121, 1122, line=162.5),
    _mk(1130, "Over Under Full Time", 1131, 1132, period="fulltime", line=160.5),       # regulation only
    _mk(1140, "Over Under 1st Half", 1141, 1142, period="p1", line=80.5),              # partial game
    _mk(1150, "Player points", 1151, 1152, line=20.5, prop=True),                      # player prop
    _mk(111, "Winner (incl. overtime)", 111, 112, mtype="moneyline", line=0.0, sides=("1", "2")),
    _mk(1200, "Total Points Over/Under 164.5", 1201, 1202, mtype=None),                # name-only catalogue
]
FIXTURES = [
    {"fixtureId": "idA", "startTime": "2024-10-03T18:00:00.000Z", "statusId": 2, "hasOdds": False,
     "participant1Name": "Real Madrid", "participant2Name": "Olympiacos Piraeus"},
    {"fixtureId": "idB", "startTime": "2024-10-03T19:30:00.000Z", "hasOdds": False,          # no statusId
     "participant1Name": "Olimpia Milano", "participant2Name": "Fenerbahçe"},
    {"fixtureId": "idC", "startTime": "2099-01-01T19:00:00.000Z", "statusId": 0,             # future
     "participant1Name": "Barcelona", "participant2Name": "Partizan"},
    {"fixtureId": "idD", "startTime": "2024-10-04T19:00:00.000Z", "statusId": 3,             # cancelled
     "participant1Name": "Monaco", "participant2Name": "Zalgiris"},
]


def _snaps(*pts):
    """(createdAt, price[, active]) tuples -> newest-first list, as the API returns them."""
    out = [{"createdAt": t, "price": p, "limit": None, **({"active": a[0]} if a else {})} for t, p, *a in pts]
    return sorted(out, key=lambda s: s["createdAt"], reverse=True)


def _hist(fid):
    if fid == "idA":
        pin = {"1110": {"outcomes": {
                   "1111": {"players": {"0": _snaps(("2024-10-02T10:00:00Z", 1.90), ("2024-10-03T17:55:00Z", 2.05),
                                                     ("2024-10-03T18:30:00Z", 3.50))}},       # in play: ignored
                   "1112": {"players": {"0": _snaps(("2024-10-02T10:00:00Z", 1.90), ("2024-10-03T17:55:00Z", 1.78))}}}},
               "1120": {"outcomes": {
                   "1121": {"players": {"0": _snaps(("2024-10-02T10:01:00Z", 2.15), ("2024-10-03T17:55:00Z", 1.92))}},
                   "1122": {"players": {"0": _snaps(("2024-10-02T10:01:00Z", 1.70), ("2024-10-03T17:55:00Z", 1.90))}}}},
               "1100": {"outcomes": {
                   "1101": {"players": {"0": _snaps(("2024-10-02T10:00:00Z", 1.70), ("2024-10-03T17:55:00Z", 1.55))}},
                   "1102": {"players": {"0": _snaps(("2024-10-02T10:00:00Z", 2.15), ("2024-10-03T17:55:00Z", 2.45))}}}},
               "1130": {"outcomes": {
                   "1131": {"players": {"0": _snaps(("2024-10-02T10:00:00Z", 1.85))}},
                   "1132": {"players": {"0": _snaps(("2024-10-02T10:00:00Z", 1.95))}}}},
               "111": {"outcomes": {"111": {"players": {"0": _snaps(("2024-10-02T10:00:00Z", 1.50))}}}},
               "1150": {"outcomes": {"1151": {"players": {"0": _snaps(("2024-10-02T10:00:00Z", 1.87))}}}},
               "77777": {"outcomes": {}}}
        b365 = {"1110": {"outcomes": {
                    "1111": {"players": {"0": _snaps(("2024-10-02T10:00:00Z", 1.87), ("2024-10-03T14:00:00Z", 2.10, False))}},
                    "1112": {"players": {"0": _snaps(("2024-10-02T10:00:00Z", 1.93), ("2024-10-03T14:00:00Z", 1.70, False))}}}},
                "1120": {"outcomes": {
                    "1121": {"players": {"0": _snaps(("2024-10-02T12:00:00Z", 1.90), ("2024-10-03T17:50:00Z", 1.91))}},
                    "1122": {"players": {"0": _snaps(("2024-10-02T12:00:00Z", 1.90), ("2024-10-03T17:50:00Z", 1.89))}}}}}
        return {"fixtureId": fid, "bookmakers": {"pinnacle": {"markets": pin}, "bet365": {"markets": b365}}}
    pin = {"1100": {"outcomes": {
               "1101": {"players": {"0": _snaps(("2024-10-02T09:00:00Z", 1.91), ("2024-10-03T19:00:00Z", 1.93))}},
               "1102": {"players": {"0": _snaps(("2024-10-02T09:00:00Z", 1.89), ("2024-10-03T19:00:00Z", 1.87))}}}}}
    return {"fixtureId": fid, "bookmakers": {"pinnacle": {"markets": pin}}}


def _route(path, params):
    if path == "/markets":
        return json.loads(json.dumps(MARKETS))
    if path == "/tournaments":
        return [{"tournamentId": 138, "tournamentSlug": "euroleague"}, {"tournamentId": 141, "tournamentSlug": "eurocup"},
                {"tournamentId": 999, "tournamentSlug": "eurocup-women"}]
    if path == "/fixtures":
        return json.loads(json.dumps(FIXTURES)) if int(params["tournamentId"]) == 138 else []
    if path == "/historical-odds":
        return _hist(params["fixtureId"])
    raise AssertionError(path)


@pytest.fixture
def api(tmp_path, monkeypatch):
    calls = []

    def fake(path, params):
        calls.append((path, dict(params)))
        return _route(path, params)

    monkeypatch.setattr(op, "RAW", tmp_path / "raw")
    monkeypatch.setattr(op, "PROC", tmp_path / "proc")
    monkeypatch.setattr(op, "_get_json", fake)
    monkeypatch.setattr(op, "seasons_to_cover", lambda first=None: [("2024-09-20", "2024-10-19")])
    return calls




def test_markets_parsing(api):
    M = op.markets().set_index("outcome_id")
    assert (M.at[1111, "kind"], M.at[1111, "line"], M.at[1111, "side"], M.at[1111, "full_game"]) == ("totals", 160.5, "over", True)
    assert M.at[1111, "incl_ot"] and not M.at[1131, "incl_ot"]
    assert not M.at[1141, "full_game"] and not M.at[1151, "full_game"]            # half / player prop
    assert (M.at[1201, "kind"], M.at[1201, "line"], M.at[1201, "full_game"]) == ("totals", 164.5, True)
    assert op.tournament_id("eurocup") == 141                                      # not the women's event


def test_update_fetches_finished_games_once_newest_first(api, tmp_path):
    got = op.update(names=("euroleague",), first="2024-09-20")
    hist = [c[1]["fixtureId"] for c in api if c[0] == "/historical-odds"]
    assert got == {"euroleague": 2} and hist == ["idA", "idB"]                    # oldest first; no future/cancelled
    assert all(c[1]["bookmakers"] == op.BOOKS for c in api if c[0] == "/historical-odds")
    cached = json.loads((tmp_path / "raw" / "138" / "hist" / "idA.json").read_text())
    kept = set(cached["bookmakers"]["pinnacle"]["markets"])
    assert {"1110", "1130", "111"} <= kept and not kept & {"1150", "77777"}      # props / unknown dropped
    assert cached["_fixture"]["participant1Name"] == "Real Madrid"
    n = len(api)
    assert op.update(names=("euroleague",), first="2024-09-20") == {"euroleague": 0}   # cached: nothing refetched
    assert not [c for c in api[n:] if c[0] == "/historical-odds"]


def test_ladder_main_lines_and_matching(api):
    op.update(names=("euroleague",), first="2024-09-20")
    G = pd.DataFrame({"game_key": ["E2024_1", "E2024_2", "E2024_3"],
                      "date": pd.to_datetime(["2024-10-03", "2024-10-03", "2024-10-03"]),
                      "home_name": ["REAL MADRID", "EA7 EMPORIO ARMANI MILAN", "PANATHINAIKOS AKTOR ATHENS"],
                      "away_name": ["OLYMPIACOS PIRAEUS", "FENERBAHCE BEKO ISTANBUL", "ANADOLU EFES ISTANBUL"]})
    L, F = op.parse(G)
    assert set(L.line) == {158.5, 160.5, 162.5}            # regulation-only line dropped where OT lines exist
    assert L.close_price.max() < 3                          # in-play snapshot ignored
    row = F.set_index(["fixture_id", "book"])
    pin = row.loc[("idA", "pinnacle")]
    assert (pin.open_line, pin.open_over, pin.close_line, pin.close_over) == (160.5, 1.90, 162.5, 1.92)
    b365 = row.loc[("idA", "bet365")]                       # 160.5 pulled before the close; 162.5 posted later
    assert (b365.open_line, b365.close_line) == (160.5, 162.5)
    assert (row.loc[("idB", "pinnacle")].open_line, row.loc[("idB", "pinnacle")].close_line) == (158.5, 158.5)
    assert F.groupby("fixture_id").game_key.first().to_dict() == {"idA": "E2024_1", "idB": "E2024_2"}


def test_name_similarity():
    assert op.name_sim("Baskonia", "KOSNER BASKONIA VITORIA-GASTEIZ") == 1.0
    assert op.name_sim("Olimpia Milano", "EA7 EMPORIO ARMANI MILAN") == 0.5
    assert op.name_sim("Fenerbahçe", "ANADOLU EFES ISTANBUL") == 0.0
    assert op.name_sim("Paris Basketball", "PARIS BASKETBALL") == 1.0


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_budget_ledger_and_key_handling(tmp_path, monkeypatch):
    seen = []

    def fake_urlopen(req, timeout=180):
        u = urllib.parse.urlparse(req.full_url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        seen.append(q)
        return _Resp(json.dumps(_route(u.path.replace("/v4", ""), q)).encode())

    monkeypatch.setattr(op, "RAW", tmp_path / "raw")
    monkeypatch.setattr(op, "MIN_INTERVAL", 0.0)
    monkeypatch.setattr(op, "seasons_to_cover", lambda first=None: [("2024-09-20", "2024-10-19")])
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setenv("ODDSPAPI_KEY", "secret-test-key")
    monkeypatch.setenv("ODDSPAPI_MONTHLY_BUDGET", "3")       # markets + fixtures + one history call
    got = op.update(names=("euroleague",), first="2024-09-20")
    assert got == {"euroleague": 1} and op.used() == 3
    assert all(q["apiKey"] == "secret-test-key" for q in seen)                     # v4: key in the query
    stored = "".join(p.read_text() for p in (tmp_path / "raw").rglob("*.json"))
    assert "secret-test-key" not in stored                                         # never written to disk
    monkeypatch.setenv("ODDSPAPI_MONTHLY_BUDGET", "5")
    assert op.update(names=("euroleague",), first="2024-09-20") == {"euroleague": 1} and op.used() == 4  # cached calls are free
    monkeypatch.delenv("ODDSPAPI_KEY")
    with pytest.raises(SystemExit):
        op._get_json("/markets", {"sportId": 11})


def test_probe_is_cheap(api, capsys):
    op.probe()
    out = capsys.readouterr().out
    assert "key OK" in out and "EuroCup tournament id: 141" in out
    assert len(api) <= 8
