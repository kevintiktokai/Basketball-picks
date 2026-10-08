import numpy as np
import pandas as pd

from data.ncaab_venue import K, venue_factor


def _hist():
    d = pd.to_datetime(["2019-11-10", "2019-12-01", "2020-01-05", "2020-01-20", "2020-02-01"])
    return pd.DataFrame({"season": "2019-20", "date": d, "home": ["eA", "eA", "eB", "eA", "eA"],
                         "neutral": [False, False, False, True, False], "total": [150.0, 140.0, 130.0, 200.0, 999.0],
                         "line_close": [140.0, 135.0, 140.0, 150.0, 100.0], "ok_close": True, "clean": True})


def test_only_earlier_home_games_count_and_shrink():
    h = _hist()
    t = pd.DataFrame({"season": "2019-20", "date": pd.to_datetime(["2020-02-01", "2019-11-10", "2020-02-01"]),
                      "home": ["eA", "eA", "eA"], "neutral": [False, False, True]})
    vf = venue_factor(h, t)
    # 2020-02-01 at A: earlier non-neutral home games of A are +10 and +5 (the neutral 2020-01-20 game and
    # the same-day game itself are excluded)
    assert np.isclose(vf[0], 15.0 / (2 + K))
    assert vf[1] == 0.0                       # first home game: no history
    assert vf[2] == 0.0                       # neutral site


def test_window_is_three_seasons_back():
    rows = []
    for y in range(2014, 2020):
        rows.append({"season": f"{y}-{(y + 1) % 100:02d}", "date": pd.Timestamp(f"{y}-12-01"), "home": "eA",
                     "neutral": False, "total": 150.0, "line_close": 140.0, "ok_close": True, "clean": True})
    h = pd.DataFrame(rows)
    t = pd.DataFrame({"season": ["2019-20"], "date": [pd.Timestamp("2020-01-15")], "home": ["eA"], "neutral": [False]})
    # seasons 2016-17, 2017-18, 2018-19 and 2019-20 to date: four games of +10
    assert np.isclose(venue_factor(h, t)[0], 40.0 / (4 + K))
