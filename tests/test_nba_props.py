"""NBA player-points props (data/nba_props.py): slimming a historical-odds response and parsing it.
The response shape follows the OddsPapi probe of 28 Oct 2026; the prices are invented."""
import json

import pandas as pd

from data import nba_props as NP


def _response():
    snap = lambda t, p: {"createdAt": t, "price": p, "limit": 250.0, "active": True}       # noqa: E731
    return {"fixtureId": "idX", "bookmakers": {
        "pinnacle": {"markets": {
            "111678": {"outcomes": {                         # Over Under Player Points 4.5
                "111678": {"players": {"1770174": [snap("2026-10-21T10:00:00Z", 1.80), snap("2026-10-22T01:00:00Z", 1.50)],
                                       "0": [snap("2026-10-21T10:00:00Z", 9.9)]}},
                "111679": {"players": {"1770174": [snap("2026-10-21T10:00:00Z", 2.05)]}}}},
            "999999": {"outcomes": {"1": {"players": {"5": [snap("2026-10-21T10:00:00Z", 1.9)]}}}}}}}}


def test_slim_keeps_pregame_player_points_only():
    keep = set(NP.points_markets().market_id)
    s = NP.slim(_response(), keep, pd.Timestamp("2026-10-21T23:59:00Z"))
    mk = s["bookmakers"]["pinnacle"]["markets"]
    assert set(mk) == {"111678"}                             # other markets dropped
    over = mk["111678"]["outcomes"]["111678"]["players"]
    assert set(over) == {"1770174"}                          # the non-player "0" key dropped
    assert len(over["1770174"]) == 1                         # in-game price (after the cut-off) dropped


def test_parse_reads_line_side_and_player(tmp_path, monkeypatch):
    monkeypatch.setattr(NP, "PROPS", tmp_path)
    monkeypatch.setattr(NP.op, "PROC", tmp_path)
    keep = set(NP.points_markets().market_id)
    s = NP.slim(_response(), keep, pd.Timestamp("2026-10-21T23:59:00Z"))
    s["_fixture"] = {"fixtureId": "idX", "startTime": "2026-10-22T00:00:00Z", "participant1Name": "A",
                     "participant2Name": "B"}
    (tmp_path / "idX__pinnacle.json").write_text(json.dumps(s))
    T = NP.parse()
    assert len(T) == 2
    assert set(zip(T.side, T.line)) == {("over", 4.5), ("under", 4.5)}
    assert set(T.player_id) == {"1770174"}
