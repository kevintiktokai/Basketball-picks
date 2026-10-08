"""1/8-Kelly stakes for the singles product (scripts/predict_cards.py)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from predict_cards import DAY_CAP, KELLY_FRACTION, single_stakes  # noqa: E402


def test_stake_is_one_eighth_kelly_at_the_offered_price():
    p, o = np.array([0.56]), np.array([1 + 100 / 110])
    full = (0.56 * o[0] - 1) / (o[0] - 1)
    assert single_stakes(p, o)[0] == pytest.approx(full * KELLY_FRACTION)        # about 0.95% of bankroll


def test_no_edge_no_stake_and_the_day_is_capped():
    assert single_stakes(np.array([0.50]), np.array([1.909]))[0] == 0.0
    f = single_stakes(np.full(40, 0.65), np.full(40, 1.909))                      # 40 strong picks
    assert f.sum() == pytest.approx(DAY_CAP) and np.allclose(f, f[0])
