"""Offline tests for the EuroLeague/EuroCup adapter (official API layouts, mocked)."""
import json

import pytest

import data.euroleague as el

RESULTS = (b'<results><game><round>RS</round><date>Oct 03, 2024</date><gamecode>E2024_1</gamecode>'
           b'<hometeam>ALBA BERLIN</hometeam><homecode>BER</homecode><homescore>77</homescore>'
           b'<awayteam>PANATHINAIKOS</awayteam><awaycode>PAN</awaycode><awayscore>87</awayscore></game></results>')
TOT = {"points": 77, "fieldGoalsMade2": 20, "fieldGoalsAttempted2": 38, "fieldGoalsMade3": 7, "fieldGoalsAttempted3": 25,
       "freeThrowsMade": 16, "freeThrowsAttempted": 20, "offensiveRebounds": 9, "defensiveRebounds": 22,
       "turnovers": 13, "foulsCommited": 21}
TOT2 = {**TOT, "points": 87, "freeThrowsAttempted": 26, "foulsCommited": 19}
GAME = {"audience": 11856, "local": {"club": {"code": "BER", "name": "ALBA Berlin"}},
        "road": {"club": {"code": "PAN", "name": "Panathinaikos"}},
        "referee1": {"name": "JAVOR, DAMIR"}, "referee2": {"name": "PEERANDI, RAIN"},
        "referee3": {"name": "SUKYS, ARTURAS"}, "referee4": None}
STATS = {"local": {"total": TOT}, "road": {"total": TOT2}}


@pytest.fixture
def api(tmp_path, monkeypatch):
    calls = []
    fail_new = {"n": 0}

    def fake(url):
        calls.append(url)
        if "/v1/results" in url:
            return RESULTS
        if url.endswith("/stats"):
            return json.dumps(STATS).encode()
        if "/v2/competitions/" in url:
            if fail_new["n"]:
                fail_new["n"] -= 1
                raise OSError("timeout")
            return json.dumps(GAME).encode()
        if "/api/Boxscore" in url:
            legacy = {"Referees": "JAVOR, DAMIR, PEERANDI, RAIN, SUKYS, ARTURAS", "Attendance": "11856",
                      "Stats": [{"totr": {k: TOT[v] for k, v in el.STATS_MAP.items()}},
                                {"totr": {k: TOT2[v] for k, v in el.STATS_MAP.items()}}]}
            return json.dumps(legacy).encode()
        raise AssertionError(url)

    monkeypatch.setattr(el, "RAW", tmp_path)
    monkeypatch.setattr(el, "_get", fake)
    monkeypatch.setattr(el.time, "sleep", lambda s: None)
    return calls, fail_new


def test_fast_path_matches_legacy_layout(api):
    calls, _ = api
    assert el.fetch_season("E2024") == 1
    assert not any("/api/Boxscore" in c for c in calls)
    G, B = el.parse(["E2024"])
    g = G.iloc[0]
    assert (g.home, g.away, g.total, g.season, g.competition) == ("BER", "PAN", 164, "2024-25", "euroleague")
    assert [g.ref1, g.ref2, g.ref3] == ["JAVOR, DAMIR", "PEERANDI, RAIN", "SUKYS, ARTURAS"]
    home = B[B.team == "BER"].iloc[0]
    assert (home.fta, home.fta_opp, home.pf) == (20, 26, 21)
    expect = 0.5 * ((63 - 9 + 13 + 0.44 * 20) + (63 - 9 + 13 + 0.44 * 26))
    assert home.poss == pytest.approx(expect)
    assert el.fetch_season("E2024") == 0                     # cached: nothing refetched


def test_legacy_fallback_when_new_api_fails(api):
    calls, fail_new = api
    fail_new["n"] = 2                                        # both fast attempts fail
    assert el.season_games("E2024") == ["1"]
    assert el.fetch_game("E2024", "1") is True
    assert any("/api/Boxscore" in c for c in calls)
    G, _ = el.parse(["E2024"])
    assert G.iloc[0].ref3 == "SUKYS, ARTURAS"


def test_current_season_list_refreshes_finished_season_does_not(api, tmp_path):
    import os
    import time
    import pandas as pd
    calls, _ = api
    now = pd.Timestamp.now()
    current = f"E{now.year if now.month >= 7 else now.year - 1}"
    for code in (current, "E2016"):
        (tmp_path / code).mkdir()
        (tmp_path / code / "results.xml").write_bytes(RESULTS)
        old = time.time() - 7 * 3600
        os.utime(tmp_path / code / "results.xml", (old, old))
    el.season_games("E2016")
    assert not any("/v1/results" in c for c in calls)        # finished season: cached for good
    el.season_games(current)
    assert any("/v1/results" in c for c in calls)            # current season: refreshed
