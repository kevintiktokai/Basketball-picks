"""Unit tests for the WNBA data rules: preseason exclusion, duplicate records, name-aware box matching."""
import pandas as pd

from data.wnba_unify import exhibition_and_duplicates, match_box_named

T = pd.Timestamp


def _box(gid, date, home, away, hp, ap, hid, aid):
    return [{"espn_game_id": gid, "date": T(date), "team_name": home, "team_id": hid, "pts": hp,
             "opp_pts": ap, "home_away": "home", "tip_time": f"{date}T19:00Z"},
            {"espn_game_id": gid, "date": T(date), "team_name": away, "team_id": aid, "pts": ap,
             "opp_pts": hp, "home_away": "away", "tip_time": f"{date}T19:00Z"}]


BOX = pd.DataFrame(_box(1, "2019-07-17", "Phoenix Mercury", "Dallas Wings", 69, 64, 11, 12)
                   + _box(2, "2019-07-18", "Los Angeles Sparks", "Dallas Wings", 69, 64, 13, 12)
                   + _box(3, "2019-07-20", "Seattle Storm", "Chicago Sky", 80, 70, 14, 15))


def _sbr(key, date, home, away, hp, ap):
    return {"game_key": key, "date": T(date), "home": home, "away": away, "home_pts": hp, "away_pts": ap}


def test_equal_scores_on_consecutive_days_are_matched_by_team_names():
    g = pd.DataFrame([_sbr("a", "2019-07-17", "Phoenix Mercury", "Dallas Wings", 69, 64),
                      _sbr("b", "2019-07-18", "Los Angeles Sparks", "Dallas Wings", 69, 64),
                      _sbr("c", "2019-07-21", "Chicago Sky", "Seattle Storm", 70, 80)])   # ESPN a day earlier, sides swapped
    m = match_box_named(g, BOX).set_index("game_key")
    assert m.loc["a", "espn_game_id"] == 1 and m.loc["b", "espn_game_id"] == 2
    assert m.loc["c", "espn_game_id"] == 3
    assert m.loc["c", "espn_home_id"] == 15 and m.loc["c", "espn_away_id"] == 14    # ids follow the SBR names


def test_preseason_and_unconfirmed_duplicates_are_dropped():
    lv = pd.DataFrame([_sbr("p", "2019-07-10", "Phoenix Mercury", "Dallas Wings", 80, 75),     # before ESPN's first game
                       _sbr("a", "2019-07-17", "Phoenix Mercury", "Dallas Wings", 69, 64),
                       _sbr("a2", "2019-07-18", "Dallas Wings", "Phoenix Mercury", 64, 69),   # same game, listed twice
                       _sbr("b", "2019-07-18", "Los Angeles Sparks", "Dallas Wings", 69, 64)])
    pre, dup = exhibition_and_duplicates(lv, BOX)
    assert list(lv.game_key[pre]) == ["p"]
    assert list(lv.game_key[dup]) == ["a2"]
