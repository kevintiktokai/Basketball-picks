"""Offline tests for the OddsPapi adapter, against responses shaped like the documented v5 API."""
import json

import pandas as pd
import pytest

import data.oddspapi as op

T0 = 1_727_960_000_000            # ms, 2024-10-03 ~13:00 UTC
MIN = 60_000

MARKETS = [
    {"marketId": 1000, "marketType": "totals", "period": "result", "handicap": 158.5, "playerProp": False,
     "outcomes": [{"outcomeId": 1001, "outcomeName": "Over"}, {"outcomeId": 1002, "outcomeName": "Under"}]},
    {"marketId": 1010, "marketType": "totals", "period": "result", "handicap": 160.5, "playerProp": False,
     "outcomes": [{"outcomeId": 1011, "outcomeName": "Over"}, {"outcomeId": 1012, "outcomeName": "Under"}]},
    {"marketId": 1020, "marketType": "totals", "period": "result", "handicap": 162.5, "playerProp": False,
     "outcomes": [{"outcomeId": 1021, "outcomeName": "Over"}, {"outcomeId": 1022, "outcomeName": "Under"}]},
    {"marketId": 1030, "marketType": "totals", "period": "fulltime", "handicap": 160.5, "playerProp": False,
     "outcomes": [{"outcomeId": 1031, "outcomeName": "Over"}, {"outcomeId": 1032, "outcomeName": "Under"}]},
    {"marketId": 1100, "marketType": "moneyline", "period": "result", "handicap": 0.0, "playerProp": False,
     "outcomes": [{"outcomeId": 1101, "outcomeName": "1"}, {"outcomeId": 1102, "outcomeName": "2"}]},
    {"marketId": 1200, "marketType": "totals", "period": "result", "handicap": 20.5, "playerProp": True,
     "outcomes": [{"outcomeId": 1201, "outcomeName": "Over"}, {"outcomeId": 1202, "outcomeName": "Under"}]},
    {"marketId": 1300, "marketType": "spreads", "period": "result", "handicap": -4.5, "playerProp": False,
     "outcomes": [{"outcomeId": 1301, "outcomeName": "1"}, {"outcomeId": 1302, "outcomeName": "2"}]},
]


def _fixture(fid, start, status, home, away, hs, as_):
    return {"fixtureId": fid, "status": {"statusId": status}, "startTime": start,
            "participants": {"participant1Name": home, "participant2Name": away},
            "scores": {"result": {"participant1Score": hs, "participant2Score": as_}} if status == 2 else {}}


FIXTURES = [_fixture("idA", 1_727_982_000, 2, "Real Madrid", "Olympiacos", 85, 80),
            _fixture("idB", 1_727_987_400, 2, "Fenerbahce", "Monaco", 70, 75),
            _fixture("idC", 1_729_800_000, 0, "Barcelona", "Partizan", None, None)]


def _o(fid, book, oid, op_, om, cp, cm, active=True):
    return {f"{fid}:{book}:{oid}:0": {
        "olv": {"bookmaker": book, "outcomeId": oid, "price": op_, "changedAt": om, "active": True},
        "clv": {"bookmaker": book, "outcomeId": oid, "price": cp, "changedAt": cm, "active": active}}}


def _clv(fid):
    odds = {}
    if fid == "idA":
        pin = {}
        for args in [(1011, 1.90, T0, 2.05, T0 + 300 * MIN), (1012, 1.90, T0, 1.78, T0 + 300 * MIN),
                     (1021, 2.15, T0 + MIN, 1.92, T0 + 300 * MIN), (1022, 1.70, T0 + MIN, 1.90, T0 + 300 * MIN),
                     (1001, 1.70, T0, 1.55, T0 + 300 * MIN), (1002, 2.15, T0, 2.45, T0 + 300 * MIN),
                     (1031, 1.85, T0, 1.85, T0 + 300 * MIN), (1032, 1.95, T0, 1.95, T0 + 300 * MIN),
                     (1101, 1.50, T0, 1.45, T0 + 300 * MIN), (1301, 1.91, T0, 1.90, T0 + 300 * MIN)]:
            pin.update(_o(fid, "pinnacle", *args))
        b365 = {}
        for args in [(1011, 1.87, T0, 2.10, T0 + 100 * MIN, False), (1012, 1.93, T0, 1.70, T0 + 100 * MIN, False),
                     (1021, 1.90, T0 + 120 * MIN, 1.91, T0 + 300 * MIN), (1022, 1.90, T0 + 120 * MIN, 1.89, T0 + 300 * MIN)]:
            b365.update(_o(fid, "bet365", *args))
        odds = {"pinnacle": pin, "bet365": b365}
    elif fid == "idB":
        pin = {}
        for args in [(1001, 1.91, T0, 1.93, T0 + 400 * MIN), (1002, 1.89, T0, 1.87, T0 + 400 * MIN),
                     (1011, 2.20, T0, 2.25, T0 + 400 * MIN), (1012, 1.65, T0, 1.62, T0 + 400 * MIN)]:
            pin.update(_o(fid, "pinnacle", *args))
        odds = {"pinnacle": pin}
    meta = next(f for f in FIXTURES if f["fixtureId"] == fid)
    return {**json.loads(json.dumps(meta)), "odds": odds}


@pytest.fixture
def api(tmp_path, monkeypatch):
    calls = []

    def fake(path, params):
        calls.append((path, dict(params)))
        if path == "/markets":
            return json.loads(json.dumps(MARKETS))
        if path == "/fixtures":
            return json.loads(json.dumps(FIXTURES))
        if path == "/fixtures/odds/clv":
            return _clv(params["fixtureId"])
        raise AssertionError(path)

    monkeypatch.setattr(op, "RAW", tmp_path / "raw")
    monkeypatch.setattr(op, "PROC", tmp_path / "proc")
    monkeypatch.setattr(op, "_get_json", fake)
    return calls


def test_fetch_is_cached_and_slim(api, tmp_path):
    assert op.fetch("euroleague", "2024-10-01", "2024-10-20") == 2          # pregame fixture skipped
    clv_calls = [c for c in api if c[0] == "/fixtures/odds/clv"]
    assert {c[1]["fixtureId"] for c in clv_calls} == {"idA", "idB"}
    cached = json.loads((tmp_path / "raw" / "138" / "clv" / "idA.json").read_text())
    ids = {int(k.split(":")[2]) for k in cached["odds"]["pinnacle"]}
    assert 1101 not in ids and 1201 not in ids and {1011, 1301} <= ids     # moneyline/props dropped
    n = len(api)
    assert op.fetch("euroleague", "2024-10-01", "2024-10-20") == 0          # resumable: nothing refetched
    assert not [c for c in api[n:] if c[0] == "/fixtures/odds/clv"]


def test_main_lines_and_matching(api):
    op.fetch("euroleague", "2024-10-01", "2024-10-20")
    G = pd.DataFrame({"game_key": ["E2024_1", "E2024_2", "E2024_9"],
                      "date": pd.to_datetime(["2024-10-03", "2024-10-03", "2024-10-10"]),
                      "home_pts": [85, 70, 85], "away_pts": [80, 75, 80]})
    L, F = op.parse("euroleague", G)
    assert set(L.line) == {158.5, 160.5, 162.5}                            # no regulation-only or prop lines
    row = F.set_index(["fixture_id", "book"])
    pin = row.loc[("idA", "pinnacle")]
    assert (pin.open_line, pin.open_over, pin.close_line, pin.close_over) == (160.5, 1.90, 162.5, 1.92)
    b365 = row.loc[("idA", "bet365")]                                       # 162.5 appeared only after the move
    assert (b365.open_line, b365.close_line) == (160.5, 162.5)
    assert (row.loc[("idB", "pinnacle")].open_line, row.loc[("idB", "pinnacle")].close_line) == (158.5, 158.5)
    keys = F.groupby("fixture_id").game_key.first().to_dict()
    assert keys == {"idA": "E2024_1", "idB": "E2024_2"}


def test_key_sent_as_header_not_in_url(monkeypatch):
    seen = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"[]"

    def fake_urlopen(req, timeout=60):
        seen["url"], seen["key"] = req.full_url, req.get_header("X-api-key")
        return Resp()

    monkeypatch.setenv("ODDSPAPI_KEY", "secret-test-key")
    monkeypatch.setattr(op, "MIN_INTERVAL", 0.0)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert op._get_json("/bookmakers", {"sportId": 11}) == []
    assert seen["key"] == "secret-test-key" and "secret-test-key" not in seen["url"]


def test_probe_runs_and_skips_womens_competitions(monkeypatch, tmp_path, capsys):
    calls = []

    def fake(path, params):
        calls.append((path, dict(params)))
        return {"/bookmakers": [{"slug": "pinnacle"}, {"slug": "bet365"}],
                "/tournaments": [{"tournamentId": 138, "tournamentSlug": "euroleague"},
                                 {"tournamentId": 141, "tournamentSlug": "eurocup"},
                                 {"tournamentId": 999, "tournamentSlug": "euroleague-women"}],
                "/markets": MARKETS, "/fixtures": FIXTURES}.get(path) or _clv(params["fixtureId"])

    monkeypatch.setattr(op, "RAW", tmp_path)
    monkeypatch.setattr(op, "_get_json", fake)
    op.probe()
    out = capsys.readouterr().out
    assert "key OK: 2 bookmakers" in out and "eurocup Nov 2018" in out
    assert not [c for c in calls if c[1].get("tournamentId") == 999]
