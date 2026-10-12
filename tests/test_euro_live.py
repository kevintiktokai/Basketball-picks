"""Live European picks (scripts/predict_euro.py): snapshot parsing, the Pinnacle whole-line
fallback, and the locked card rules applied to a live board. No network: odds are invented."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from predict_euro import locked_cfg, picks  # noqa: E402

from data import oddsapi  # noqa: E402
from features.euro_market import fair_curve  # noqa: E402


def _book(key, line, o, u):
    return {"key": key, "markets": [{"key": "totals", "outcomes": [{"name": "Over", "price": o, "point": line},
                                                                   {"name": "Under", "price": u, "point": line}]}]}


def _snapshot(tmp_path, games):
    t = pd.Timestamp("2026-10-12 12:00", tz="UTC")
    p = tmp_path / f"basketball_euroleague_{t:%Y%m%dT%H%M%SZ}.json"
    p.write_text(json.dumps([{"id": gid, "commence_time": start, "home_team": h, "away_team": a,
                              "bookmakers": [_book(*b) for b in books]} for gid, start, h, a, books in games]))
    return p


def test_board_parses_books_lines_and_sides(tmp_path):
    p = _snapshot(tmp_path, [("g1", "2026-10-13T18:00:00Z", "Home", "Away",
                              [("pinnacle", 161.5, 1.9, 1.95), ("onexbet", 160.5, 1.98, 1.84), ("unibet_eu", 162.5, 1.8, 2.0)])])
    B = oddsapi.board(p)
    assert set(B.book) == {"pinnacle", "1xbet", "unibet"}
    assert len(B) == 6 and set(B.side) == {"over", "under"}
    assert B.t.iloc[0] == pd.Timestamp("2026-10-12 12:00", tz="UTC")


def test_whole_pinnacle_line_is_used_only_when_asked(tmp_path):
    p = _snapshot(tmp_path, [("g1", "2026-10-13T18:00:00Z", "Home", "Away", [("pinnacle", 174.0, 1.92, 1.94)])])
    B = oddsapi.board(p)
    assert fair_curve(B).empty                                    # backtests: half-point lines only
    c = fair_curve(B, whole_lines=True)
    assert c.fair_mu.iloc[0] == pytest.approx(174.0, abs=0.5)


def test_locked_card_needs_model_agreement_and_odds_band(tmp_path):
    games = [("g1", "2026-10-13T18:00:00Z", "A", "B", [("pinnacle", 161.5, 1.90, 1.95), ("onexbet", 160.5, 1.98, 1.84)]),
             ("g2", "2026-10-13T18:30:00Z", "C", "D", [("pinnacle", 174.5, 1.92, 1.94), ("onexbet", 173.5, 2.02, 1.80)]),
             ("g3", "2026-10-13T19:00:00Z", "E", "F", [("pinnacle", 165.5, 1.93, 1.93), ("onexbet", 167.5, 1.80, 2.02)])]
    B = oddsapi.board(_snapshot(tmp_path, games))
    # the model agrees with the Overs in g1 and g2, and disagrees with g3's value Under
    model = pd.Series({"g1": 163.0, "g2": 177.0, "g3": 168.0})
    L, C, S, _ = picks(B, model, locked_cfg())
    assert len(C) == 1
    assert {C.iloc[0].game_a, C.iloc[0].game_b} == {"g1", "g2"}
    assert C.iloc[0].odds == pytest.approx(1.98 * 2.02)
    assert "g3" in set(S.fixture_id)                              # singles need value only
    assert not S.set_index("fixture_id").model_agrees["g3"]
